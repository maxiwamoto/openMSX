// BSD 3-Clause License
//
// Copyright (c) 2021, Aaron Giles
// All rights reserved.
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions are met:
//
// 1. Redistributions of source code must retain the above copyright notice, this
//    list of conditions and the following disclaimer.
//
// 2. Redistributions in binary form must reproduce the above copyright notice,
//    this list of conditions and the following disclaimer in the documentation
//    and/or other materials provided with the distribution.
//
// 3. Neither the name of the copyright holder nor the names of its
//    contributors may be used to endorse or promote products derived from
//    this software without specific prior written permission.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
// AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
// IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
// DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
// FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
// DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
// SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
// CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
// OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
// OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

#include "MSXMakoto.hh"

#include "DeviceConfig.hh"
#include "Clock.hh"
#include "ResampledSoundDevice.hh"
#include "Schedulable.hh"
#include "IRQHelper.hh"
#include "Ram.hh"
#include "Rom.hh"
#include "SimpleDebuggable.hh"
#include "StringOp.hh"
#include "serialize.hh"
#include "serialize_meta.hh"
#include "serialize_stl.hh"
#include "3rdparty/ymfm/ymfm_opn.h"
#include "3rdparty/ym2608/fmopn_2608rom.h"

#include <algorithm>
#include <array>
#include <vector>
#include <numbers>

namespace openmsx {
// Cartridge integration is separate from the pinned YMFM core (see README.openmsx).
class MakotoSound final : private ymfm::ymfm_interface
{
	static constexpr unsigned CLOCK = 8000000;
	static constexpr uint8_t STATUS_ADPCM_B_EOS = 0x04;
	static constexpr uint8_t STATUS_ADPCM_B_BRDY = 0x08;
	static constexpr uint8_t STATUS_ADPCM_B_PLAYING = 0x20;
	using fm_engine = ymfm::fm_engine_base<ymfm::opna_registers>;

	// Both hardware streams have symmetric ownership and independent clocks.
	class Part : public ResampledSoundDevice
	{
	public:
		Part(DeviceConfig& config, std::string_view name, static_string_view description,
		     unsigned channels, unsigned rate, bool stereo)
		    : ResampledSoundDevice(config.getMotherBoard(), name, description, channels, rate, stereo)
		{
		}
		// Expose SoundDevice::updateStream(), which synchronizes all sound devices.
		void sync(EmuTime time) { updateStream(time); }
		void restoreClock(EmuTime time)
		{
			createResampler();
			getEmuClock().reset(time);
		}
		void rate(unsigned value)
		{
			if (getInputRate() != value) {
				setInputRate(value);
				createResampler();
			}
		}
		void setOutputRate(unsigned rate, double speed) override
		{
			const auto previous = getEmuClock();
			ResampledSoundDevice::setOutputRate(rate, speed);
			// A newly constructed clock has period zero, so it cannot match
			// a real sample period. No separate initialization flag is needed.
			if (previous.getPeriod() == getEmuClock().getPeriod()) {
				getEmuClock().reset(previous.getTime());
			}
		}
	};

	class FmPart final : public Part
	{
	public:
		FmPart(DeviceConfig& config, std::string_view name, MakotoSound& owner_)
		    : Part(config, name, "Makoto FM, rhythm and ADPCM", 13, (CLOCK + 72) / 144, true),
		      fm(owner_), adpcmA(owner_, 0), adpcmB(owner_), owner(owner_)
		{
			registerSound(config);
		}
		~FmPart() { unregisterSound(); }

		fm_engine fm;
		ymfm::adpcm_a_engine adpcmA;
		ymfm::adpcm_b_engine adpcmB;

	private:
		void generateChannels(std::span<float*> buffers, unsigned num) override;
		template <bool Combined> void generateImpl(std::span<float*> buffers, unsigned num);
		MakotoSound& owner;
	};

	class SsgPart final : public Part
	{
	public:
		SsgPart(DeviceConfig& config, std::string_view name, MakotoSound& owner)
		    : Part(config, strCat(name, " SSG"), "Makoto SSG", 3, CLOCK / 32, false), ssg(owner)
		{
			registerSound(config);
		}
		~SsgPart() { unregisterSound(); }
		ymfm::ssg_engine ssg;

	private:
		float getAmplificationFactorImpl() const override
		{
			// Maximum normalization. Standard SSG volume replaces the old trim.
			return std::numbers::sqrt2_v<float> * (2.0f / 3.0f) / (32768.0f * 4.3f);
		}
		void generateChannels(std::span<float*> buffers, unsigned num) override;
		template <bool Combined> void generateImpl(std::span<float*> buffers, unsigned num);
	};

	class Timer final : public Schedulable
	{
	public:
		Timer(Scheduler& scheduler, MakotoSound& owner_, unsigned index_)
		    : Schedulable(scheduler), owner(owner_), index(index_)
		{
		}

		void cancel() { removeSyncPoints(); }
		void schedule(EmuTime time)
		{
			cancel();
			setSyncPoint(time);
		}
		template <typename Archive> void serialize(Archive& ar, unsigned /*version*/)
		{
			ar.template serializeBase<Schedulable>(*this);
		}

	private:
		void executeUntil(EmuTime time) override
		{
			owner.updateStream(time);
			owner.contextTime = time;
			// YMFM reloads the timer through ymfm_set_timer().
			owner.m_engine->engine_timer_expired(index);
		}

		MakotoSound& owner;
		const unsigned index;
	};

public:
	MakotoSound(DeviceConfig& config, std::string_view name, EmuTime time)
	    : irq(config.getMotherBoard(), strCat(name, ".IRQ")),
	      timers{Timer(config.getScheduler(), *this, 0), Timer(config.getScheduler(), *this, 1)},
	      contextTime(time), busyEnd(time),
	      sampleRAM(config, strCat(name, " ADPCM RAM"), "YM2608 ADPCM-B sample RAM", 262144),
	      registers(config.getMotherBoard(), name, *this), fmPart(config, name, *this),
	      ssgPart(config, name, *this)
	{
		if (config.findChild("rom")) {
			rhythm = std::make_unique<Rom>(strCat(name, " rhythm ROM"),
						       "YM2608 internal rhythm samples", config);
			if (rhythm->size() != 8192)
				throw MSXException("Makoto rhythm ROM must be 8192 bytes");
		}
		sampleRAM.clear(0); // Deterministic emulator policy; hardware power-on contents are unknown.
		reset(time);
	}

	void reset(EmuTime time)
	{
		updateStream(time);
		contextTime = time;
		for (auto& timer : timers)
			timer.cancel();
		resetChip();
		applyRates();
		busyEnd = time;
		irq.reset();
	}
	byte read(unsigned port, EmuTime time)
	{
		updateStream(time);
		contextTime = time;
		return readChip(port);
	}
	byte peek(unsigned port, EmuTime time) { return peekChip(port, time < busyEnd); }
	void write(unsigned port, byte value, EmuTime time)
	{
		updateStream(time);
		contextTime = time;
		writeChip(port, value);
		applyRates();
	}
	template <typename Archive> void serialize(Archive& ar, unsigned version)
	{
		if constexpr (!Archive::IS_LOADER) updateStream(timers[0].getCurrentTime());
		// Version 3 uses native timers and class versioning for the pinned core.
		// Public versions 1/2 stored absolute deadlines; preserve those on load.
		if (ar.versionAtLeast(version, 3)) {
			ar.serialize("timerA", timers[0], "timerB", timers[1]);
		} else if constexpr (Archive::IS_LOADER) {
			if (ar.versionAtLeast(version, 2)) {
				unsigned coreFormat = 1;
				ar.serialize("coreFormat", coreFormat);
				if (coreFormat != 1)
					throw MSXException("Unsupported Makoto core state format");
			}
			std::array<EmuTime, 2> deadlines = {EmuTime::infinity(), EmuTime::infinity()};
			ar.serialize("deadlines", deadlines);
			for (unsigned i = 0; i < 2; ++i) {
				timers[i].cancel();
				if (deadlines[i] != EmuTime::infinity()) timers[i].schedule(deadlines[i]);
			}
		}
		std::vector<uint8_t> legacyCore;
		if (ar.versionAtLeast(version, 10)) {
			ChipState state{*this};
			ar.serialize("chip", state);
		} else if constexpr (Archive::IS_LOADER) {
			ar.serialize("core", legacyCore);
		}
		ar.serialize("busyEnd", busyEnd);
		if (ar.versionAtLeast(version, 6)) {
			ar.serialize("sampleRAM", sampleRAM);
		} else if constexpr (Archive::IS_LOADER) {
			// Public fork versions 1-5 stored one XML item per byte.
			auto legacy = std::make_unique<std::array<byte, 262144>>();
			ar.serialize("sampleRAM", *legacy);
			std::ranges::copy(*legacy, sampleRAM.begin());
		}
		ar.serialize("irq", irq, "sampleClock", fmPart.getEmuClock());
		if (ar.versionAtLeast(version, 8)) ar.serialize("ssgClock", ssgPart.getEmuClock());
		if constexpr (Archive::IS_LOADER) {
			if (ar.versionAtLeast(version, 2) && !ar.versionAtLeast(version, 9)) {
				std::array<int32_t, 32> legacyOutput{};
				ar.serialize("channelOutput", legacyOutput);
			}
		}
		if constexpr (Archive::IS_LOADER) {
			if (!ar.versionAtLeast(version, 10)) {
				// Versions 1-6 did not store the unfinished CPU-write latch.
				if (!ar.versionAtLeast(version, 7)) {
					legacyCore.push_back(0);
				}
				if (legacyCore.size() != 1134) {
					throw MSXException("Invalid legacy Makoto core state size");
				}
				ymfm::ymfm_saved_state saved(legacyCore, false);
				restoreLegacyState(saved);
			}
			// Restore rates before reinstating the saved sample-clock phases.
			const auto fmTime = fmPart.getEmuClock().getTime();
			const auto ssgTime =
				ar.versionAtLeast(version, 8) ? ssgPart.getEmuClock().getTime() : fmTime;
			applyRates();
			// Old releases stored a 1 MHz clock; reconstruct the native periods.
			ssgPart.restoreClock(ssgTime);
			fmPart.restoreClock(fmTime);
			fmPart.fm.invalidate_caches();
			contextTime = timers[0].getCurrentTime();
		}
	}

private:
	struct ChipState
	{
		MakotoSound& owner;
		template <typename Archive> void serialize(Archive& ar, unsigned /*version*/)
		{
			ar.serialize("address", owner.address, "irqEnable", owner.irqEnable, "flagControl",
				     owner.flagControl);
			serializeEngine(ar, "fm", owner.fmPart.fm);
			serializeEngine(ar, "ssg", owner.ssgPart.ssg);
			serializeEngine(ar, "adpcmA", owner.fmPart.adpcmA);
			serializeEngine(ar, "adpcmB", owner.fmPart.adpcmB);
			if constexpr (Archive::IS_LOADER) owner.updatePrescale(owner.prescale());
		}
	};
	void resetChip();
	void restoreLegacyState(ymfm::ymfm_saved_state& state);
	unsigned prescale() const { return fmPart.fm.clock_prescale(); }
	unsigned fmRate() const { return (CLOCK + 12 * prescale()) / (24 * prescale()); }
	unsigned ssgRate() const { return CLOCK / (prescale() == 6 ? 32 : prescale() == 3 ? 16 : 8); }
	uint8_t readChip(uint32_t offset);
	uint8_t peekChip(uint32_t offset, bool busy) const;
	uint8_t peekRegister(uint16_t regnum) const;
	void writeChip(uint32_t offset, uint8_t data);
	void writeRegister(uint16_t regnum, uint8_t data);
	template <typename Archive, typename Engine>
	static void serializeEngine(Archive& ar, const char* name, Engine& engine)
	{
		// Obtain the pinned engine's exact byte count. The archive's blob reader
		// rejects a mismatched length instead of YMFM silently zero-filling it.
		std::vector<uint8_t> data;
		ymfm::ymfm_saved_state saved(data, true);
		engine.save_restore(saved);
		ar.serialize_blob(name, std::span<uint8_t>(data), false);
		if constexpr (Archive::IS_LOADER) {
			ymfm::ymfm_saved_state restored(data, false);
			engine.save_restore(restored);
		}
	}
	uint8_t readStatus();
	uint8_t readStatusHi();
	uint8_t readData();
	uint8_t readDataHi();
	[[nodiscard]] uint8_t statusHi() const;
	void writeAddress(uint8_t data);
	void writeAddressHi(uint8_t data);
	void writeData(uint8_t data);
	void writeDataHi(uint8_t data);
	void updatePrescale(uint8_t prescale);

	void ymfm_set_timer(uint32_t timer, int32_t duration) override
	{
		if (duration < 0)
			timers[timer].cancel();
		else
			timers[timer].schedule(contextTime + Clock<CLOCK>::duration(unsigned(duration)));
	}
	void ymfm_set_busy_end(uint32_t duration) override
	{
		busyEnd = contextTime + Clock<CLOCK>::duration(duration);
	}
	bool ymfm_is_busy() override { return contextTime < busyEnd; }
	void ymfm_update_irq(bool asserted) override { irq.set(asserted); }
	uint8_t ymfm_external_peek(ymfm::access_class type, uint32_t sampleAddress) override
	{
		// Both sample stores are passive memory; GPIO is unconnected.
		return ymfm_external_read(type, sampleAddress);
	}
	uint8_t ymfm_external_read(ymfm::access_class type, uint32_t sampleAddress) override
	{
		if (type == ymfm::ACCESS_ADPCM_B) return sampleRAM[sampleAddress & 0x3ffff];
		if (type == ymfm::ACCESS_ADPCM_A)
			return rhythm ? (*rhythm)[sampleAddress & 0x1fff]
				      : YM2608_ADPCM_ROM[sampleAddress & 0x1fff];
		return 0xff; // SSG GPIO is not attached to the MSX keyboard or joysticks.
	}
	void ymfm_external_write(ymfm::access_class type, uint32_t sampleAddress, uint8_t value) override
	{
		if (type == ymfm::ACCESS_ADPCM_B) sampleRAM[sampleAddress & 0x3ffff] = value;
	}
	void updateStream(EmuTime time) { fmPart.sync(time); }
	void applyRates()
	{
		fmPart.rate(fmRate());
		ssgPart.rate(ssgRate());
	}

	struct Registers final : SimpleDebuggable
	{
		Registers(MSXMotherBoard& board, std::string_view name, MakotoSound& owner_)
		    : SimpleDebuggable(board, strCat(name, " registers"), "Effective YM2608 core registers",
				       512),
		      owner(owner_)
		{
		}
		byte read(unsigned address) override { return owner.peekRegister(uint16_t(address)); }
		void write(unsigned address, byte value, EmuTime time) override
		{
			owner.updateStream(time);
			owner.contextTime = time;
			owner.writeRegister(uint16_t(address), value);
			owner.applyRates();
		}
		MakotoSound& owner;
	};
	IRQHelper irq;
	std::array<Timer, 2> timers;
	EmuTime contextTime;
	EmuTime busyEnd;
	uint16_t address = 0;
	uint8_t irqEnable = 0x1f;
	uint8_t flagControl = 0x1c;
	Ram sampleRAM;
	std::unique_ptr<Rom> rhythm;
	Registers registers;
	FmPart fmPart;
	SsgPart ssgPart;
};

using namespace ymfm;

void MakotoSound::resetChip()
{
	// reset the engines
	fmPart.fm.reset();
	ssgPart.ssg.reset();
	fmPart.adpcmA.reset();
	fmPart.adpcmB.reset();

	// configure ADPCM percussion sounds; these are present in an embedded ROM
	fmPart.adpcmA.set_start_end(0, 0x0000, 0x01bf); // bass drum
	fmPart.adpcmA.set_start_end(1, 0x01c0, 0x043f); // snare drum
	fmPart.adpcmA.set_start_end(2, 0x0440, 0x1b7f); // top cymbal
	fmPart.adpcmA.set_start_end(3, 0x1b80, 0x1cff); // high hat
	fmPart.adpcmA.set_start_end(4, 0x1d00, 0x1f7f); // tom tom
	fmPart.adpcmA.set_start_end(5, 0x1f80, 0x1fff); // rim shot

	// initialize our special interrupt states, then read the upper status
	// register, which updates the IRQs
	irqEnable = 0x1f;
	flagControl = 0x1c;
	readStatusHi();
}

void MakotoSound::restoreLegacyState(ymfm_saved_state& state)
{
	state.save_restore(address);
	state.save_restore(irqEnable);
	state.save_restore(flagControl);
	std::array<int32_t, 2> legacyFm{};
	for (auto& value : legacyFm)
		state.save_restore(value);

	fmPart.fm.save_restore(state);
	ssgPart.ssg.save_restore(state);
	uint32_t legacyIndex = 0;
	std::array<int32_t, 3> legacySsg{};
	state.save_restore(legacyIndex);
	for (auto& value : legacySsg)
		state.save_restore(value);
	fmPart.adpcmA.save_restore(state);
	fmPart.adpcmB.save_restore(state);
	// Keep engine prescaler notification consistent after legacy-state restore.
	// No repeated-sample or SSG resampler configuration exists in this layer.
	if (!state.saving()) {
		updatePrescale(fmPart.fm.clock_prescale());
	}
}

uint8_t MakotoSound::readStatus()
{
	uint8_t result = fmPart.fm.status() & (fm_engine::STATUS_TIMERA | fm_engine::STATUS_TIMERB);
	if (fmPart.fm.intf().ymfm_is_busy()) {
		result |= fm_engine::STATUS_BUSY;
	}
	return result;
}

uint8_t MakotoSound::readData()
{
	if (address < 0x10) {
		return ssgPart.ssg.read(address & 0x0f);
	} else {
		return address == 0xff ? 1 : 0;
	}
}

uint8_t MakotoSound::statusHi() const
{
	// fetch regular status
	uint8_t status =
		fmPart.fm.status() & ~(STATUS_ADPCM_B_EOS | STATUS_ADPCM_B_BRDY | STATUS_ADPCM_B_PLAYING);

	// fetch ADPCM-B status, and merge in the bits
	uint8_t adpcmStatus = fmPart.adpcmB.status();
	if ((adpcmStatus & adpcm_b_channel::STATUS_EOS) != 0) {
		status |= STATUS_ADPCM_B_EOS;
	}
	if ((adpcmStatus & adpcm_b_channel::STATUS_BRDY) != 0) {
		status |= STATUS_ADPCM_B_BRDY;
	}
	if ((adpcmStatus & adpcm_b_channel::STATUS_PLAYING) != 0) {
		status |= STATUS_ADPCM_B_PLAYING;
	}

	// turn off any bits that have been requested to be masked
	status &= ~(flagControl & 0x1f);

	return status;
}

uint8_t MakotoSound::readStatusHi()
{
	uint8_t status = statusHi();

	// update the status so that IRQs are propagated
	fmPart.fm.set_reset_status(status, ~status);

	// merge in the busy flag
	if (fmPart.fm.intf().ymfm_is_busy()) {
		status |= fm_engine::STATUS_BUSY;
	}
	return status;
}

uint8_t MakotoSound::readDataHi()
{
	if ((address & 0xff) < 0x10) {
		return fmPart.adpcmB.read(address & 0x0f);
	} else {
		return 0;
	}
}

uint8_t MakotoSound::readChip(uint32_t offset)
{
	uint8_t result = 0;
	switch (offset & 3) {
	case 0: // status port, YM2203 compatible
		result = readStatus();
		break;

	case 1: // data port (only SSG)
		result = readData();
		break;

	case 2: // status port, extended
		result = readStatusHi();
		break;

	case 3: // ADPCM-B data
		result = readDataHi();
		break;
	}
	return result;
}

// Debugger reads deliberately bypass readStatusHi()'s IRQ update and the
// ADPCM data port's dummy reads, address advancement and flag changes.
uint8_t MakotoSound::peekChip(uint32_t offset, bool busy) const
{
	switch (offset & 3) {
	case 0:
		return (fmPart.fm.status() & (fm_engine::STATUS_TIMERA | fm_engine::STATUS_TIMERB)) |
		       (busy ? fm_engine::STATUS_BUSY : 0);
	case 1:
		if (address < 0x10) {
			return ssgPart.ssg.peek(address);
		}
		return (address == 0xff) ? 1 : 0;
	case 2:
		return statusHi() | (busy ? fm_engine::STATUS_BUSY : 0);
	case 3:
		return ((address & 0xff) < 0x10) ? fmPart.adpcmB.peek(address & 0x0f) : 0;
	}
	return 0;
}

// openMSX: normal port-write behavior without disturbing a pending CPU write.
void MakotoSound::writeRegister(uint16_t regnum, uint8_t data)
{
	uint16_t savedAddress = address;
	uint32_t port = (regnum & 0x100) ? 2 : 0;
	writeChip(port, uint8_t(regnum));
	writeChip(port + 1, data);
	address = savedAddress;
}

uint8_t MakotoSound::peekRegister(uint16_t regnum) const
{
	assert(regnum < 0x200);
	if (regnum < 0x10) {
		return ssgPart.ssg.regs().read(regnum);
	}
	if (regnum < 0x20) {
		return fmPart.adpcmA.regs().read(regnum & 0x0f);
	}
	if (regnum == 0x29) {
		return irqEnable;
	}
	if (regnum >= 0x100 && regnum < 0x110) {
		return fmPart.adpcmB.regs().read(regnum & 0x0f);
	}
	if (regnum == 0x110) {
		return flagControl;
	}
	return fmPart.fm.regs().read(regnum);
}

void MakotoSound::writeAddress(uint8_t data)
{
	// just set the address
	address = data;

	// special case: update the prescale
	if (address >= 0x2d && address <= 0x2f) {
		// 2D-2F: prescaler select
		if (address == 0x2d) {
			updatePrescale(6);
		} else if (address == 0x2e && fmPart.fm.clock_prescale() == 6) {
			updatePrescale(3);
		} else if (address == 0x2f) {
			updatePrescale(2);
		}
	}
}

void MakotoSound::writeData(uint8_t data)
{
	// ignore if paired with upper address
	if (bitfield(address, 8)) {
		return;
	}

	if (address < 0x10) {
		// 00-0F: write to SSG
		ssgPart.ssg.write(address & 0x0f, data);
	} else if (address < 0x20) {
		// 10-1F: write to ADPCM-A
		fmPart.adpcmA.write(address & 0x0f, data);
	} else if (address == 0x29) {
		// 29: special IRQ mask register
		irqEnable = data;
		fmPart.fm.set_irq_mask(irqEnable & ~flagControl & 0x1f);
	} else {
		// 20-28, 2A-FF: write to FM
		fmPart.fm.write(address, data);
	}

	// mark busy for a bit
	fmPart.fm.intf().ymfm_set_busy_end(32 * fmPart.fm.clock_prescale());
}

void MakotoSound::writeAddressHi(uint8_t data)
{
	// just set the address
	address = 0x100 | data;
}

void MakotoSound::writeDataHi(uint8_t data)
{
	// ignore if paired with upper address
	if (!bitfield(address, 8)) {
		return;
	}

	if (address < 0x110) {
		// 100-10F: write to ADPCM-B
		fmPart.adpcmB.write(address & 0x0f, data);
	} else if (address == 0x110) {
		// 110: IRQ flag control
		if (bitfield(data, 7)) {
			fmPart.fm.set_reset_status(0, 0xff);
		} else {
			flagControl = data;
			fmPart.fm.set_irq_mask(irqEnable & ~flagControl & 0x1f);
		}
	} else {
		// 111-1FF: write to FM
		fmPart.fm.write(address, data);
	}

	// mark busy for a bit
	fmPart.fm.intf().ymfm_set_busy_end(32 * fmPart.fm.clock_prescale());
}

void MakotoSound::writeChip(uint32_t offset, uint8_t data)
{
	switch (offset & 3) {
	case 0: // address port
		writeAddress(data);
		break;

	case 1: // data port
		writeData(data);
		break;

	case 2: // upper address port
		writeAddressHi(data);
		break;

	case 3: // upper data port
		writeDataHi(data);
		break;
	}
}

void MakotoSound::updatePrescale(uint8_t prescale)
{
	fmPart.fm.set_clock_prescale(prescale);
	ssgPart.ssg.prescale_changed();
}

template <bool Combined> void MakotoSound::FmPart::generateImpl(std::span<float*> buffers, unsigned num)
{
	uint32_t orOutput = 0;
	const uint32_t fmMask = bitfield(owner.irqEnable, 7) ? 0x3f : 0x07;
	for (unsigned i = 0; i < num; ++i) {
		const auto env = fm.clock(fm_engine::ALL_CHANNELS);
		if (bitfield(env, 0, 2) == 0) {
			adpcmA.clock(bitfield(env, 2) ? 0x0f : 0x3f);
		}
		adpcmB.clock();
		if constexpr (Combined) {
			// No channel tools: render each engine once into a local stereo sum.
			// This is not retained chip state, and is never internally clipped.
			fm_engine::output_data mixed;
			fm.output(mixed.clear(), 1, 32767, fmMask);
			adpcmB.output(mixed, 1);
			adpcmA.output(mixed, 0x3f);
			buffers[0][2 * i] += float(mixed.data[0]);
			buffers[0][2 * i + 1] += float(mixed.data[1]);
			orOutput |= uint32_t(mixed.data[0] | mixed.data[1]);
		} else {
			// Six FM voices, one ADPCM-B voice and six rhythm voices.
			// Write directly to the host buffers; no channel-output cache.
			fm_engine::output_data voice;
			for (unsigned c = 0; c < 6; ++c) {
				fm.output(voice.clear(), 1, 32767, fmMask & (1U << c));
				buffers[c][2 * i] += float(voice.data[0]);
				buffers[c][2 * i + 1] += float(voice.data[1]);
			}
			adpcmB.output(voice.clear(), 1);
			buffers[6][2 * i] += float(voice.data[0]);
			buffers[6][2 * i + 1] += float(voice.data[1]);
			for (unsigned c = 0; c < 6; ++c) {
				adpcmA.output(voice.clear(), 1U << c);
				buffers[c + 7][2 * i] += float(voice.data[0]);
				buffers[c + 7][2 * i + 1] += float(voice.data[1]);
			}
		}
	}
	if constexpr (Combined) {
		std::ranges::fill(buffers.subspan(1), nullptr);
		if (!orOutput) {
			buffers[0] = nullptr;
		}
	}
}

void MakotoSound::FmPart::generateChannels(std::span<float*> buffers, unsigned num)
{
	assert(buffers.size() == 13);
	if (std::ranges::all_of(buffers, [&](auto* b) { return b == buffers[0]; })) {
		generateImpl<true>(buffers, num);
	} else {
		generateImpl<false>(buffers, num);
	}
}

template <bool Combined> void MakotoSound::SsgPart::generateImpl(std::span<float*> buffers, unsigned num)
{
	uint32_t orOutput = 0;
	for (unsigned i = 0; i < num; ++i) {
		ssg_engine::output_data s;
		ssg.clock();
		ssg.output(s);
		if constexpr (Combined) {
			const auto total = s.data[0] + s.data[1] + s.data[2];
			buffers[0][i] += float(total);
			orOutput |= uint32_t(total);
		} else {
			for (unsigned c = 0; c < 3; ++c)
				buffers[c][i] += float(s.data[c]);
		}
	}
	if constexpr (Combined) {
		std::ranges::fill(buffers.subspan(1), nullptr);
		if (!orOutput) {
			buffers[0] = nullptr;
		}
	}
}

void MakotoSound::SsgPart::generateChannels(std::span<float*> buffers, unsigned num)
{
	assert(buffers.size() == 3);
	if (std::ranges::all_of(buffers, [&](auto* b) { return b == buffers[0]; })) {
		generateImpl<true>(buffers, num);
	} else {
		generateImpl<false>(buffers, num);
	}
}

// Versions 1/2 were distributed in the public Makoto preview builds.
// Version 6 stores sample RAM as a delta-compressed blob; older saves still load.
// Experimental version 8 adds a separately clocked native SSG stream.
// Version 9 removes the unused separated-output cache; old states still load.
// Version 10 uses native control fields and separate engine blobs.
SERIALIZE_CLASS_VERSION(MakotoSound, 10);

MSXMakoto::MSXMakoto(DeviceConfig& config)
    : MSXDevice(config), sound(std::make_unique<MakotoSound>(config, getName(), getCurrentTime()))
{
}
MSXMakoto::~MSXMakoto() = default;
void MSXMakoto::reset(EmuTime time)
{
	sound->reset(time);
}
byte MSXMakoto::readIO(uint16_t port, EmuTime time)
{
	return sound->read(port & 3, time);
}
byte MSXMakoto::peekIO(uint16_t port, EmuTime time) const
{
	return sound->peek(port & 3, time);
}
void MSXMakoto::writeIO(uint16_t port, byte value, EmuTime time)
{
	sound->write(port & 3, value, time);
}
template <typename Archive> void MSXMakoto::serialize(Archive& ar, unsigned /*version*/)
{
	ar.template serializeBase<MSXDevice>(*this);
	ar.serialize("sound", *sound);
}
INSTANTIATE_SERIALIZE_METHODS(MSXMakoto);
REGISTER_MSXDEVICE(MSXMakoto, "Makoto");
} // namespace openmsx
