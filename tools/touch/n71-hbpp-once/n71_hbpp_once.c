// SPDX-License-Identifier: GPL-2.0-only
/*
 * N71/S8000 experimental single-use HBPP status-only controller ID probe.
 *
 * Requires the live-verified kernel #5 with Z2 child DT disabled.
 * Operates on an isolated SPI child, never binds the production Z2 driver.
 * Controller version is read only after strict HBPP status/checksum validation.
 * NO Apple proprietary firmware, calibration, HBPP writes, NAND, or baseband IO.
 *
 * A 1500 ms independent delayed work guards the 20ms analog/clock experiment.
 * Only one context owns shutdown, so clock framework counts cannot underflow.
 * This module persists inert after the first run (CONFIG_MODULE_UNLOAD=n).
 */
#include <linux/atomic.h>
#include <linux/bitops.h>
#include <linux/clk.h>
#include <linux/clk-provider.h>
#include <linux/completion.h>
#include <linux/delay.h>
#include <linux/device.h>
#include <linux/errno.h>
#include <linux/gpio/consumer.h>
#include <linux/i2c.h>
#include <linux/io.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_clk.h>
#include <linux/regmap.h>
#include <linux/spi/spi.h>
#include <linux/string.h>
#include <linux/unaligned.h>
#include <linux/workqueue.h>

#define PFX "n71_hbpp_once: "
#define PMGR_PHYS 0x20e078000ULL
#define GPIO_PHYS 0x20f100000ULL
#define GPIO_RESET75 75
#define PMGR_BASE 0x800002eeU
#define PMGR_ACTIVE 0x000802dcU
#define RESET_BASE 0x00072202U
#define ANALOG_BASE 0x0f
#define ANALOG_ACTIVE 0x1f
#define CORE_BASE 0x01
#define SPI_HZ 1000000U
#define HBPP_READ_DATA 0x4c39U
#define HBPP_VERSION_ADDR 0x10008ffcU
#define HBPP_APU_ADDR 0x10003800U
#define WATCHDOG_MS 1500U

struct n71_state {
	struct clk *clk;
	struct gpio_desc *reset;
	struct i2c_client *chestnut;
	struct spi_controller *ctlr;
	struct spi_device *spi;
	struct delayed_work watchdog;
	struct completion watchdog_done;
	atomic_t restore_owner;
	bool clock_enabled;
	bool watchdog_scheduled;
	bool analog_touched;
	int experiment_result;
};

static struct n71_state g;

static u32 read_mmio_word(phys_addr_t base, u32 offset)
{
	void __iomem *p = ioremap(base + offset, 4);
	u32 value;

	if (!p)
		return ~0U;
	value = readl(p);
	iounmap(p);
	return value;
}

static int analog_read(void)
{
	if (!g.chestnut)
		return -ENODEV;
	return i2c_smbus_read_byte_data(g.chestnut, 0x05);
}

static int check_baseline(const char *phase)
{
	u32 clock = read_mmio_word(PMGR_PHYS, 0);
	u32 reset = read_mmio_word(GPIO_PHYS, GPIO_RESET75 * 4);
	int analog = analog_read();

	pr_info(PFX "%s clk=%08x reset=%08x analog=%02x\n",
		phase, clock, reset, analog);
	if (clock != PMGR_BASE || reset != RESET_BASE ||
	    analog != ANALOG_BASE)
		return -EUCLEAN;
	return 0;
}

static void analog_restore(const char *who)
{
	int v, ret, i;

	if (!g.chestnut)
		return;
	for (i = 0; i < 3; i++) {
		v = analog_read();
		if (v == ANALOG_BASE) {
			pr_info(PFX "%s ANALOG_RESTORED=%02x\n", who, v);
			return;
		}
		if (v != ANALOG_ACTIVE) {
			pr_err(PFX "%s REFUSE_RESTORE: unexpected analog=%d\n",
			       who, v);
			return;
		}
		ret = i2c_smbus_write_byte_data(g.chestnut, 0x05, ANALOG_BASE);
		if (ret) {
			pr_err(PFX "%s analog_restore_write=%d attempt=%d\n",
				who, ret, i + 1);
			continue;
		}
		usleep_range(1000, 1500);
	}
	pr_err(PFX "%s ANALOG_RESTORE_RETRIES_EXHAUSTED\n", who);
}

static void shutdown_hardware(const char *who)
{
	if (atomic_cmpxchg(&g.restore_owner, 0, 1) != 0)
		return;
	pr_info(PFX "%s SHUTDOWN_BEGIN\n", who);

	if (g.reset) {
		gpiod_set_value_cansleep(g.reset, 1); /* active-low reset asserted */
		usleep_range(1000, 2000);
	}
	if (READ_ONCE(g.clock_enabled)) {
		clk_disable_unprepare(g.clk);
		WRITE_ONCE(g.clock_enabled, false);
	}
	analog_restore(who);
	pr_info(PFX "%s SHUTDOWN_DONE\n", who);
}

static void independent_watchdog(struct work_struct *work)
{
	int err;

	/* Preempt the one-shot transaction if the primary loader stalled. */
	if (atomic_read(&g.restore_owner) == 0) {
		pr_err(PFX "WATCHDOG_TIMEOUT: forcing bounded hardware cleanup\n");
		shutdown_hardware("WATCHDOG");
	}
	err = check_baseline("WATCHDOG_AUDIT");
	if (err)
		pr_err(PFX "WATCHDOG_FAIL_BASELINE=%d\n", err);
	else
		pr_info(PFX "WATCHDOG_AUDIT_PASS\n");
	complete(&g.watchdog_done);
}

static int spi_word_xfer(const u8 *tx, u8 *rx, u32 length)
{
	struct spi_transfer t = {
		.tx_buf = tx,
		.rx_buf = rx,
		.len = length,
		.speed_hz = SPI_HZ,
		.bits_per_word = 8,
	};

	if (atomic_read(&g.restore_owner))
		return -ECANCELED;
	if (length > 16)
		return -E2BIG;
	return spi_sync_transfer(g.spi, &t, 1);
}

static bool known_hbpp_status(u16 status)
{
	switch (status) {
	case 0x18e1: /* NOP */
	case 0x1aa1: /* ATN */
	case 0x1f01: /* REQ_CAL */
	case 0x4879: /* IDLE */
	case 0x4969:
	case 0x4ad1: /* ACK_REG */
	case 0x4bc1: /* ACK_DATA */
	case 0x4c39: /* READ_DATA */
		return true;
	default:
		return false;
	}
}

static void make_check_packet(u8 tx[16])
{
	int i;
	tx[0] = 0x1a; tx[1] = 0xa1;
	for (i = 2; i < 16; i += 2) {
		tx[i] = 0x18; tx[i + 1] = 0xe1;
	}
}

static int strict_hbpp_read(u32 address, u32 *value)
{
	u8 cmd[8] = { 0x1c, 0x73 };
	u8 status_cmd[8] = { 0x1a, 0xa1, 0x18, 0xe1,
			     0x18, 0xe1, 0x18, 0xe1 };
	u8 reply[8] = {};
	u16 sum = 0, returned_sum, status;
	int i, error;

	put_unaligned_be16((u16)address, cmd + 2);
	put_unaligned_be16((u16)(address >> 16), cmd + 4);
	for (i = 2; i < 6; i++)
		sum += cmd[i];
	put_unaligned_be16(sum, cmd + 6);

	error = spi_word_xfer(cmd, reply, sizeof(cmd));
	if (error)
		return error;
	memset(reply, 0, sizeof(reply));
	error = spi_word_xfer(status_cmd, reply, sizeof(status_cmd));
	if (error)
		return error;

	status = get_unaligned_be16(reply);
	returned_sum = get_unaligned_be16(reply + 6);
	sum = 0;
	for (i = 2; i < 6; i++)
		sum += reply[i];

	pr_info(PFX "MEM_READ addr=%08x status=%04x checksum=%04x expected=%04x\n",
		address, status, returned_sum, sum);
	if (status != HBPP_READ_DATA || returned_sum != sum) {
		pr_err(PFX "REJECT_INVALID_READ_REPLY addr=%08x\n", address);
		return -EBADMSG;
	}

	*value = get_unaligned_be16(reply + 2) |
		((u32)get_unaligned_be16(reply + 4) << 16);
	return 0;
}

static int status_only_probe(void)
{
	u8 tx[16], rx[16] = {};
	u16 first, second;
	u32 version = 0, apu = 0;
	int i, err;

	/* The reset pin is still asserted. This clocks idle SCK mode 3. */
	make_check_packet(tx);
	err = spi_word_xfer(tx, rx, sizeof(tx));
	if (err)
		return err;
	pr_info(PFX "IN_RESET_PRIME_XFER_PASS\n");

	gpiod_set_value_cansleep(g.reset, 0); /* deassert active-low reset */
	msleep(15);
	pr_info(PFX "RESET_DEASSERTED_15MS\n");
	if (atomic_read(&g.restore_owner))
		return -ETIMEDOUT;

	for (i = 0; i < 2; i++) {
		make_check_packet(tx);
		memset(rx, 0, sizeof(rx));
		err = spi_word_xfer(tx, rx, sizeof(tx));
		if (err)
			return err;
		first = get_unaligned_be16(rx);
		second = get_unaligned_be16(rx + 2);
		pr_info(PFX "STATUS_CHECK_%d first=%04x second=%04x\n",
			i, first, second);
		if (!known_hbpp_status(first) || !known_hbpp_status(second))
			return -EPROTO;
		usleep_range(1000, 1500);
	}

	memset(rx, 0, sizeof(rx));
	tx[0] = 0x1a; tx[1] = 0xa1;
	err = spi_word_xfer(tx, rx, 2);
	if (err)
		return err;
	first = get_unaligned_be16(rx);
	pr_info(PFX "ATN_STATUS=%04x\n", first);
	if (!known_hbpp_status(first))
		return -EPROTO;

	err = strict_hbpp_read(HBPP_VERSION_ADDR, &version);
	if (err)
		return err;
	if (!version || version == ~0U) {
		pr_err(PFX "REJECT_INVALID_CONTROLLER_VERSION=%08x\n", version);
		return -EBADMSG;
	}
	pr_info(PFX "VALID_CONTROLLER_VERSION=%08x\n", version);
	if (version == 0x434d15c1U)
		pr_info(PFX "VERSION_MATCHES_PRIOR_N71_DIAGNOSTIC\n");

	err = strict_hbpp_read(HBPP_APU_ADDR, &apu);
	if (err)
		return err;
	pr_info(PFX "VALID_APU_READ_VALUE=%08x\n", apu);
	return 0;
}

static void free_resources(void)
{
	if (g.spi) {
		spi_unregister_device(g.spi);
		g.spi = NULL;
	}
	if (g.ctlr) {
		put_device(&g.ctlr->dev);
		g.ctlr = NULL;
	}
	if (g.reset) {
		gpiod_put(g.reset);
		g.reset = NULL;
	}
	if (g.clk) {
		clk_put(g.clk);
		g.clk = NULL;
	}
	if (g.chestnut) {
		i2c_unregister_device(g.chestnut);
		g.chestnut = NULL;
	}
}

static int __init n71_init(void)
{
	struct device_node *touch = NULL, *ctrl = NULL, *clk_node = NULL;
	struct of_phandle_args spec = {};
	struct spi_board_info info = {
		.modalias = "n71-hbpp-once",
		.chip_select = 0,
		.max_speed_hz = SPI_HZ,
		.mode = SPI_MODE_3,
	};
	struct i2c_adapter *bus;
	struct device *pmu;
	struct regmap *pmumap;
	u32 pmu219, pmu319, pmgr, resetreg;
	int err = -EPERM, analog;
	unsigned long completed = 0;

	pr_info(PFX "BEGIN STRICT_STATUS_ONLY_ONE_SHOT, NO FIRMWARE OR NAND\n");
	atomic_set(&g.restore_owner, 0);
	init_completion(&g.watchdog_done);
	touch = of_find_node_by_path("/soc/spi@20a088000/touchscreen@0");
	ctrl = of_find_node_by_path("/soc/spi@20a088000");
	clk_node = of_find_node_by_path(
		"/soc/power-management@20e000000/clock-controller@78000");
	if (!touch || !ctrl || !clk_node ||
	    of_device_is_available(touch) ||
	    !of_device_is_available(ctrl) ||
	    !of_device_is_available(clk_node)) {
		pr_err(PFX "REFUSED: no expected isolated N71 Device Tree\n");
		goto out;
	}

	pmgr = read_mmio_word(PMGR_PHYS, 0);
	resetreg = read_mmio_word(GPIO_PHYS, GPIO_RESET75 * 4);
	pr_info(PFX "PRE_CLK=%08x PRE_RESET=%08x\n", pmgr, resetreg);
	if (pmgr != PMGR_BASE || resetreg != RESET_BASE) {
		pr_err(PFX "REFUSED: unexpected PMGR/reset baseline\n");
		goto out;
	}

	pmu = bus_find_device_by_name(&i2c_bus_type, NULL, "0-0074");
	if (!pmu) {
		err = -ENODEV;
		goto out;
	}
	pmumap = dev_get_regmap(pmu, NULL);
	if (!pmumap) {
		put_device(pmu);
		err = -ENODEV;
		goto out;
	}
	err = regmap_read(pmumap, 0x219, &pmu219);
	if (!err)
		err = regmap_read(pmumap, 0x319, &pmu319);
	put_device(pmu);
	if (err)
		goto out;
	pr_info(PFX "PRE_CORE_219=%02x CORE_319=%02x\n", pmu219, pmu319);
	if (pmu219 != 0 || pmu319 != CORE_BASE) {
		err = -EPERM;
		goto out;
	}

	bus = i2c_get_adapter(0);
	if (!bus) {
		err = -ENODEV;
		goto out;
	}
	g.chestnut = i2c_new_dummy_device(bus, 0x27);
	i2c_put_adapter(bus);
	if (IS_ERR(g.chestnut)) {
		err = PTR_ERR(g.chestnut);
		g.chestnut = NULL;
		goto out;
	}
	analog = analog_read();
	if (analog != ANALOG_BASE) {
		pr_err(PFX "REFUSED: analog baseline=%d\n", analog);
		err = -EPERM;
		goto out;
	}

	/* This acquires the ACTIVE_LOW reset pin without changing direction.
	 * It must already be a physically low OUTPUT (held in reset).
	 */
	g.reset = fwnode_gpiod_get_index(of_fwnode_handle(touch), "reset",
					0, GPIOD_ASIS, "n71-hbpp-once");
	if (IS_ERR(g.reset)) {
		err = PTR_ERR(g.reset);
		g.reset = NULL;
		goto out;
	}
	if (gpiod_get_direction(g.reset) != 0 ||
	    gpiod_get_raw_value(g.reset) != 0) {
		pr_err(PFX "REFUSED: reset not asserted output\n");
		err = -EPERM;
		goto out;
	}

	spec.np = clk_node;
	spec.args_count = 0;
	g.clk = of_clk_get_from_provider(&spec);
	if (IS_ERR(g.clk)) {
		err = PTR_ERR(g.clk);
		g.clk = NULL;
		goto out;
	}
	if (strcmp(__clk_get_name(g.clk), "touch_ref") ||
	    clk_get_rate(g.clk) > 40000) {
		pr_err(PFX "REFUSED: wrong touch reference clock\n");
		err = -EPERM;
		goto out;
	}

	g.ctlr = of_find_spi_controller_by_node(ctrl);
	if (!g.ctlr) {
		err = -ENODEV;
		goto out;
	}
	g.spi = spi_new_device(g.ctlr, &info);
	if (!g.spi) {
		err = -ENODEV;
		goto out;
	}
	g.spi->cs_setup.value = 5000;
	g.spi->cs_setup.unit = SPI_DELAY_UNIT_NSECS;
	g.spi->cs_hold.value = 10000;
	g.spi->cs_hold.unit = SPI_DELAY_UNIT_NSECS;
	g.spi->bits_per_word = 8;
	err = spi_setup(g.spi);
	pr_info(PFX "SPI_SETUP_1MHZ_MODE3=%d\n", err);
	if (err)
		goto out;
	if (check_baseline("PREFLIGHT")) {
		err = -EUCLEAN;
		goto out;
	}

	INIT_DELAYED_WORK(&g.watchdog, independent_watchdog);
	g.watchdog_scheduled =
		schedule_delayed_work(&g.watchdog,
				      msecs_to_jiffies(WATCHDOG_MS));
	if (!g.watchdog_scheduled) {
		err = -EBUSY;
		goto out;
	}

	pr_info(PFX "ARMED 1500MS INDEPENDENT BACKUP\n");
	err = i2c_smbus_write_byte_data(g.chestnut, 0x05, ANALOG_ACTIVE);
	g.analog_touched = true;
	if (err) {
		pr_err(PFX "ANALOG_ENABLE_WRITE_FAILED=%d\n", err);
		goto cleanup;
	}
	analog = analog_read();
	if (analog != ANALOG_ACTIVE) {
		pr_err(PFX "ANALOG_ACTIVE_READBACK_FAILED=%d\n", analog);
		err = -EIO;
		goto cleanup;
	}
	pr_info(PFX "ANALOG_ACTIVE=%02x\n", analog);
	usleep_range(2000, 5000);

	err = clk_prepare_enable(g.clk);
	if (err) {
		pr_err(PFX "CLOCK_ENABLE_FAILED=%d\n", err);
		goto cleanup;
	}
	g.clock_enabled = true;
	usleep_range(1000, 2000);
	pmgr = read_mmio_word(PMGR_PHYS, 0);
	if (pmgr != PMGR_ACTIVE) {
		pr_err(PFX "CLOCK_ACTIVE_READBACK_FAILED=%08x\n", pmgr);
		err = -EIO;
		goto cleanup;
	}
	pr_info(PFX "CLOCK_ACTIVE=%08x\n", pmgr);
	err = status_only_probe();
	if (!err)
		pr_info(PFX "PASS: HBPP_STATUS_AND_BOTH_STRICT_READS_VALID\n");
	else
		pr_err(PFX "STATUS_PROBE_FAILED=%d\n", err);

cleanup:
	g.experiment_result = err;
	shutdown_hardware("DIRECT");
	completed = wait_for_completion_timeout(&g.watchdog_done,
						 msecs_to_jiffies(3000));
	if (!completed) {
		pr_err(PFX "WATCHDOG_NO_COMPLETION; hold resources for safety\n");
		/* Fail safely: do not free resources accessed by delayed worker. */
		goto out;
	}
	if (check_baseline("FINAL")) {
		pr_err(PFX "CRITICAL_FINAL_BASELINE_MISMATCH\n");
		g.experiment_result = -EUCLEAN;
	} else {
		pr_info(PFX "FINAL_BOARD_BASELINE_PASS\n");
	}
out:
	of_node_put(touch);
	of_node_put(ctrl);
	of_node_put(clk_node);
	/* Only release tracked resources after the watchdog has completed. */
	if (!g.watchdog_scheduled || completed) {
		free_resources();
		pr_info(PFX "RELEASED_SPI_GPIO_CLOCK_AND_I2C_RESOURCES\n");
	}
	pr_info(PFX "COMPLETE protocol_result=%d (module deliberately inert)\n",
		g.experiment_result ? g.experiment_result : err);
	/* Always succeed init to ensure the BusyBox insmod caller cannot rerun
	 * a physically stateful probe automatically after a negative retval.
	 */
	return 0;
}
module_init(n71_init);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("N71 bounded, fail-closed, strict-checksum HBPP identification single shot");
