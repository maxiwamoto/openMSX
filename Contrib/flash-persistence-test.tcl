# Used by flash-persistence-test.py. All profiles and ROMs are disposable.
set renderer none
set throttle off
set save_settings_on_exit false
set mute on
set power on
source $::env(FLASH_PLAN)
proc finish {message} {
    if {$message ne "OK"} {store_machine [machine] "$::env(FLASH_RESULT).oms"}
    set f [open $::env(FLASH_RESULT) w]
    puts $f $message
    close $f
    exit
}
proc map_flash {address} {
    if {$::env(FLASH_MAPPER) eq "Yamanooto"} {
        # Keep bank 0 mapped at 4000h for unlock commands. Access the save
        # through an independent 8 KiB window, including banks above 2 MiB.
        set bank [expr {$address >> 13}]
        debug write memory 0x7fff 1
        debug write memory 0x7ffe 0
        debug write memory 0x7ffd 0
        debug write memory 0x5000 0
        debug write memory 0x7ffe [expr {($bank >> 8) << 6}]
        debug write memory 0x9000 [expr {$bank & 255}]
        debug write memory 0x7fff 0x11
        return [expr {0x8000 | ($address & 0x1fff)}]
    }
    set bank [expr {$address >> 14}]
    debug write memory [expr {0x6000 | ($bank & 0xf00)}] [expr {$bank & 255}]
    return [expr {0x4000 | ($address & 0x3fff)}]
}
proc unlock {command} {
    debug write memory 0x4aaa 0xaa
    debug write memory 0x4555 0x55
    debug write memory 0x4aaa $command
}
proc ram_call {entry} {
    if {$::env(FLASH_RAM_ROUTINES) eq ""} {error "Missing RAM routine binary"}
    set f [open $::env(FLASH_RAM_ROUTINES) rb]
    set code [read $f]
    close $f
    debug write_block memory 0xc200 $code
    # Capture AF without changing flags, then write a completion marker and spin.
    debug write_block memory 0xc180 [binary format H* f5e122f0c13ea532f2c1c38ac1]
    debug write memory 0xc1f2 0
    debug write_block memory 0xfdfe [binary format H* 80c1]
    reg SP 0xfdfe
    # Page 1: bank 0 for unlock addresses. Page 2: bank 8 (physical 020000).
    if {$::env(FLASH_MAPPER) eq "Yamanooto"} {
        # Same RAM routines and physical save sector, using four 8 KiB banks.
        debug write memory 0x7fff 1
        debug write memory 0x7ffe 0
        debug write memory 0x7ffd 0
        foreach {register bank} {0x5000 0 0x7000 1 0x9000 16 0xb000 17} {
            debug write memory $register $bank
        }
        debug write memory 0x7fff 0x11
    } else {
        debug write memory 0x6000 0
        debug write memory 0x7000 8
    }
    reg PC $entry
}
proc step {} {
    if {![llength $::actions]} {finish OK; return}
    if {[catch {
        set action [lindex $::actions 0]
        set ::actions [lrange $::actions 1 end]
        set delay 0.001
        switch [lindex $action 0] {
            expect {
                lassign $action op address expected
                set actual [debug read memory [map_flash $address]]
                if {$actual != $expected} {error [format "At %06x: expected %02x, got %02x" $address $expected $actual]}
            }
            program {
                lassign $action op address value
                set cpu [map_flash $address]
                unlock 0xa0
                debug write memory $cpu $value
                set delay 0.01
            }
            erase {
                set cpu [map_flash [lindex $action 1]]
                unlock 0x80
                debug write memory 0x4aaa 0xaa
                debug write memory 0x4555 0x55
                debug write memory $cpu 0x30
                set delay 2.0
            }
            ram-program - ram-program-pending {
                set bytes {}
                for {set i 0} {$i < 256} {incr i} {lappend bytes $i}
                debug write_block memory 0xc800 [binary format c* $bytes]
                reg HL 0xc800
                reg DE 0x8100
                reg BC 256
                if {[lindex $action 0] eq "ram-program-pending"} {
                    # Capture during the actual first program operation, not at
                    # a guessed CPU offset that differs between Flash chips.
                    set ::pending_watch [debug set_watchpoint write_mem 0x8100 {1} {
                        debug remove_watchpoint $::pending_watch
                        after time 0.000002 step
                    }]
                    ram_call 0xc200
                    set delay -1
                } else {
                    ram_call 0xc200
                    set delay 1.0
                }
            }
            wait {set delay [lindex $action 1]}
            ram-erase {ram_call 0xc203; set delay 2.0}
            ram-status {
                lassign $action op status expected
                debug write memory 0xc900 $status
                reg A $expected
                reg DE 0xc900
                reg BC 0x1234
                ram_call 0xc206
                set delay 0.01
            }
            ram-result {
                if {[debug read memory 0xc1f2] != 0xa5} {error "RAM routine did not return"}
                set flags [debug read memory 0xc1f0]
                if {($flags & 1) != [lindex $action 1]} {error "Wrong carry: $flags"}
                if {[reg SP] != 0xfe00} {error "Stack not balanced"}
            }
            ram-data - ram-erased {
                for {set i 0} {$i < 256} {incr i} {
                    set actual [debug read memory [map_flash [expr {0x20100+$i}]]]
                    set expected [expr {[lindex $action 0] eq "ram-data" ? $i : 255}]
                    if {$actual != $expected} {error "Byte $i: expected $expected got $actual"}
                }
            }
            ram-status-byte {
                if {[debug read memory 0xc900] != [lindex $action 1]} {error "Wrong reset/status byte"}
                if {[reg BC] != 0x1234} {error "Status routine changed BC"}
            }
            save {store_machine [machine] [lindex $action 1]}
            load {
                set previous [machine]
                set restored [restore_machine [lindex $action 1]]
                delete_machine $previous
                activate_machine $restored
            }
            default {error "Unknown action: $action"}
        }
        if {$delay >= 0} {after time $delay step}
    } problem]} {finish "FAIL: $problem
$::errorInfo"}
}
after time 1 {
    if {[catch {
        # BIOS has configured RAM in page 3. Run a DI/spin loop there while Flash
        # is busy, mapping cartridge slot 1 into pages 1 and 2.
        debug write_block memory 0xc100 [binary format H* f3c301c1]
        reg PC 0xc100
        reg SP 0xff00
        debug write ioports 0xa8 0xd4
        after time 0.01 step
    } problem]} {finish "FAIL: $problem
$::errorInfo"}
}
