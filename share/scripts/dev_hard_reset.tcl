# Development hard reset: reopen cartridge/floppy files during a power cycle.
set_help_text dev_hard_reset \
{Power-cycles the MSX and reloads every inserted ROM cartridge from its current
host file, retaining slots, mapper types and IPS patches. Remounts file-backed
floppy disk images too. With no media inserted, performs a power cycle. Missing/empty files abort before switching power off.
Uses the cartridge's normal SRAM/Flash persistence. Leaves RAM disks and directory disks mounted. Does not
refresh system firmware, hard disks or cassette images. Current gameplay restarts.}

proc dev_hard_reset {} {
    set reloads [list]
    foreach media [machine_info media] {
        if {![string match cart? $media]} continue
        set info [machine_info media $media]
        if {![dict exists $info type] || [dict get $info type] ne "rom"} continue
        set filename [dict get $info target]
        set patches [dict get $info patches]
        # Validate every source before changing power or removing cartridges.
        foreach path [linsert $patches 0 $filename] {
            if {![file isfile $path] || ![file readable $path] || [file size $path] == 0} {
                error "Cannot hard reset: file is missing, empty or unreadable: $path"
            }
        }
        set command [list $media insert $filename -romtype [dict get $info mappertype]]
        foreach patch $patches {lappend command -ips $patch}
        lappend reloads $command
    }
    set disks [list]
    foreach media [machine_info media] {
        if {![string match disk? $media]} continue
        set info [machine_info media $media]
        if {[dict get $info type] ne "file"} continue
        set filename [dict get $info target]
        set patches [list]
        if {[dict exists $info patches]} {set patches [dict get $info patches]}
        foreach path [linsert $patches 0 $filename] {
            if {![file isfile $path] || ![file readable $path] || [file size $path] == 0} {
                error "Cannot hard reset: file is missing, empty or unreadable: $path"
            }
        }
        lappend disks [list $media insert $filename {*}$patches]
    }
    set power off
    try {
        # Release all disk references first, including shared decompression caches.
        foreach command $disks {[lindex $command 0] eject}
        # Drop all ROM references before reopening shared compressed images.
        # Ejecting cartridges flushes their normal persistent data.
        foreach command $reloads {[lindex $command 0] eject}
        foreach command $reloads {{*}$command}
        foreach command $disks {{*}$command}
    } finally {
        # Do not leave the MSX powered off if an insertion reports an error.
        set power on
    }
    message "Hard reset: reloaded [llength $reloads] ROM cartridge(s), [llength $disks] disk image(s), and powered on."
}
