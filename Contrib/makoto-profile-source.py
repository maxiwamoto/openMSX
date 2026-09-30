"""Generate a temporary instrumented Makoto wrapper; do not ship it.

Counters observe raw DAC clipping without changing synthesis. Host CPU benchmarks
must use an uninstrumented executable. The generated source depends on the current
wrapper structure and deliberately fails if the expected insertion points move.
"""
import argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
s=(ROOT/'src/sound/MSXMakoto.cc').read_text()
needle='\t\t, registers(config.getMotherBoard(), *this)';assert needle in s
s=s.replace(needle,needle+'\n\t\t, profile(config.getMotherBoard(), *this)')
needle='\tvoid generateChannels(';assert needle in s
helper="""	void countProfile(const ymfm::ym2608::output_data& output)
	{
		++profileCounters[0];
		if (!chip.channel_output_changed()) return;
		++profileCounters[1];
		for (unsigned side = 0; side < 2; ++side) {
			int total = 0;
			for (unsigned c = 0; c < 16; ++c) {
				if (c < 6 || c >= 9) total += channelOutput[2 * c + side];
			}
			if (total != output.data[side]) ++profileCounters[2 + side];
			profileCounters[4 + side] = std::max(profileCounters[4 + side], uint64_t(total < 0 ? -total : total));
		}
	}
"""
s=s.replace(needle,helper+needle)
assert s.count('chip.generate(&output);')==2
s=s.replace('chip.generate(&output);','chip.generate(&output); countProfile(output);')
s=s.replace('mix.update(channelOutput, ssg.data, output.data, ssgGain);','++profileCounters[6]; mix.update(channelOutput, ssg.data, output.data, ssgGain);')
needle='\tRegisters registers;';assert needle in s
profile="""	std::array<uint64_t, 7> profileCounters = {};
	struct Profile final : SimpleDebuggable {
		Profile(MSXMotherBoard& board, MakotoSound& owner_)
			: SimpleDebuggable(board, "Makoto profile", "Temporary clipping counters (7 little-endian uint64)", 56), owner(owner_) {}
		byte read(unsigned address) override {
			return byte(owner.profileCounters[address / 8] >> (8 * (address % 8)));
		}
		void write(unsigned address, byte value) override {
			if (address == 0 && value == 0) owner.profileCounters.fill(0);
		}
		MakotoSound& owner;
	} profile;
"""
s=s.replace(needle,needle+'\n'+profile)
a.output.write_text(s)
print(a.output)
