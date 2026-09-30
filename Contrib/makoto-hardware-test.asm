; Makoto YM2608 ADPCM-B boundary probe. Original synthetic test; no game data.
; Build: tniasm compat.asm Contrib/makoto-hardware-test.asm output.rom
; Cold power-on required: the first status reads happen before OPNA writes.
; Uses only 16h/17h, avoiding the Music Module collision at 14h.
; V5: explicit ADPCM reset before each mode, verified by V4 on physical Makoto.
; Baseline and reseed checks gate interpretation of the boundary rows.
%symfile "derived/makoto-hardware-test.sym"
        org     4000h
        db      "AB"
        dw      boot,0000h,0000h,0000h,0000h,0000h,0000h
RESULT          equ     0C100h
RESET_STATUS    equ     RESULT+10h
OPEN_STATUS     equ     RESULT+18h
END_BYTES       equ     RESULT+20h
LIMIT_BYTES     equ     RESULT+28h
TIMED_OUT       equ     RESULT+04h
BASE_OK         equ     RESULT+05h
SEED_OK         equ     RESULT+06h
BASE_BYTES      equ     RESULT+30h
SEED_BYTES      equ     RESULT+38h
END_ADDRESS     equ     RESULT+40h
LIMIT_ADDRESS   equ     RESULT+42h
TRANSFER_MODE   equ     RESULT+44h
WRITE_COUNT     equ     RESULT+45h
END_COUNT       equ     RESULT+46h
CHGMOD          equ     005Fh
CHPUT           equ     00A2h

boot:
        di
        ld      sp,0F300h
        ld      a,(002Dh)
        cp      03h
        jr      nz,z80_ready
        ld      a,80h
        call    0180h           ; Turbo-R: use Z80 for conservative I/O spacing.
z80_ready:
        di
        ld      hl,RESULT
        ld      de,RESULT+01h
        ld      bc,004Fh
        ld      (hl),00h
        ldir
        ld      hl,END_BYTES
        ld      b,10h
        ld      a,0EEh          ; EE means boundary test was skipped.
preset_skipped:
        ld      (hl),a
        inc     hl
        djnz    preset_skipped
        ld      hl,RESET_STATUS
        call    status_eight    ; No OPNA writes precede these reads.
        ld      a,(RESET_STATUS)
        cp      0FFh
        jp      z,no_chip
        ld      b,10h
        xor     a
        call    write_high
        ld      hl,OPEN_STATUS
        call    status_eight
        call    full_range
        ld      hl,seed_c
        ld      c,08h
        call    write_block
        ld      hl,BASE_BYTES
        call    read_eight
        ld      hl,BASE_BYTES
        ld      de,seed_c
        call    compare_eight
        ld      (BASE_OK),a
        or      a
        jp      z,tests_done
        ld      a,(TIMED_OUT)
        or      a
        jp      nz,tests_done
        ld      hl,seed_ff
        ld      c,08h
        call    write_block
        ld      hl,0000h
        ld      (END_ADDRESS),hl
        ld      hl,seed_a
        ld      c,04h
        call    write_block
        ld      a,(WRITE_COUNT)
        ld      (END_COUNT),a
        call    full_range
        ld      hl,END_BYTES
        call    read_eight
        ld      hl,seed_b
        ld      c,08h
        call    write_block
        ld      hl,SEED_BYTES
        call    read_eight
        ld      hl,SEED_BYTES
        ld      de,seed_b
        call    compare_eight
        ld      (SEED_OK),a
        or      a
        jr      z,tests_done
        ld      a,(TIMED_OUT)
        or      a
        jr      nz,tests_done
        ld      hl,0000h
        ld      (LIMIT_ADDRESS),hl
        ld      hl,LIMIT_BYTES
        call    read_eight
tests_done:
        ; BIOS can enable interrupts. Release OPNA /IRQ before display calls.
        ld      b,10h
        ld      a,1Fh
        call    write_high
        jr      display
no_chip:
        ld      a,01h
        ld      (TIMED_OUT),a

display:
        ld      hl,signature
        ld      de,RESULT
        ld      bc,0004h
        ldir
        xor     a
        ld      (0F3DBh),a      ; Disable BIOS key click.
        ld      (0F3EAh),a
        ld      (0F3EBh),a
        ld      a,0Fh
        ld      (0F3E9h),a
        ld      a,28h
        ld      (0F3AEh),a
        xor     a
        call    CHGMOD
        di
        ld      hl,title
        call    text
        ld      hl,label_reset
        call    text
        ld      hl,RESET_STATUS
        call    print_eight
        ld      hl,label_open
        call    text
        ld      hl,OPEN_STATUS
        call    print_eight
        ld      hl,label_base
        call    text
        ld      hl,BASE_BYTES
        call    print_eight
        ld      hl,label_end
        call    text
        ld      hl,END_BYTES
        call    print_eight
        ld      hl,label_seed
        call    text
        ld      hl,SEED_BYTES
        call    print_eight
        ld      hl,label_limit
        call    text
        ld      hl,LIMIT_BYTES
        call    print_eight
        ld      hl,label_timeout
        call    text
        ld      a,(TIMED_OUT)
        call    hex_byte
        ld      hl,label_checks
        call    text
        ld      a,(BASE_OK)
        call    hex_byte
        ld      a,20h
        call    put
        ld      a,(SEED_OK)
        call    hex_byte
        ld      a,20h
        call    put
        ld      a,(END_COUNT)
        call    hex_byte
        ld      hl,footer
        call    text
idle:
        ei
        halt
        jr      idle

full_range:
        ld      hl,0FFFFh
        ld      (END_ADDRESS),hl
        ld      (LIMIT_ADDRESS),hl
        ret
compare_eight:
        ld      b,08h
compare_loop:
        ld      a,(de)
        cp      (hl)
        jr      nz,compare_failed
        inc     de
        inc     hl
        djnz    compare_loop
        ld      a,01h
        ret
compare_failed:
        xor     a
        ret
; A=20h read / 60h write. Preserve caller's data pointer and byte count.
setup_transfer:
        push    hl
        push    bc
        ld      (TRANSFER_MODE),a
        call    end_transfer
        ld      b,10h
        ld      a,13h
        call    write_high      ; Expose EOS and BRDY.
        ld      a,80h
        call    write_high      ; Reset flags, retain mask.
        ld      b,00h
        ld      a,(TRANSFER_MODE)
        call    write_high      ; Mode before memory type and addresses.
        ld      b,01h
        xor     a              ; DRAM x1, no audio output.
        call    write_high
        ld      b,02h
        call    write_high
        ld      b,03h
        call    write_high      ; Start = 0000h.
        ld      b,04h
        ld      a,(END_ADDRESS)
        call    write_high
        inc     b
        ld      a,(END_ADDRESS+01h)
        call    write_high
        ld      b,0Ch
        ld      a,(LIMIT_ADDRESS)
        call    write_high
        inc     b
        ld      a,(LIMIT_ADDRESS+01h)
        call    write_high
        ; V4 row C/D: a stop alone is insufficient before read mode on hardware.
        ld      b,00h
        ld      a,01h
        call    write_high
        ld      a,(TRANSFER_MODE)
        call    write_high
        pop     bc
        pop     hl
        ret
end_transfer:
        ld      b,00h
        xor     a
        call    write_high
        ld      b,10h
        ld      a,80h
        jp      write_high
write_block:
        xor     a
        ld      (WRITE_COUNT),a
        ld      a,60h
        call    setup_transfer
        ld      b,10h
        ld      a,14h          ; Same reset/ready writer as V4 C/D.
        call    write_high
write_loop:
        call    wait_brdy
        ld      b,08h
        ld      a,(hl)
        inc     hl
        call    write_high
        ld      a,(WRITE_COUNT)
        inc     a
        ld      (WRITE_COUNT),a
        dec     c
        jr      z,write_done
        ld      b,10h
        ld      a,0F0h
        call    write_high
        jr      write_loop
write_done:
        ; At the end boundary EOS may signal completion. Preserve that flag
        ; after the final byte and accept EOS or BRDY, rather than clearing it.
        call    transfer_ready
        jp      end_transfer
wait_brdy:
        push    af
        push    de
        ld      de,1000h
brdy_poll:
        in      a,(16h)
        and     08h
        jr      nz,brdy_done
        dec     de
        ld      a,d
        or      e
        jr      nz,brdy_poll
        ld      a,(TIMED_OUT)
        or      02h
        ld      (TIMED_OUT),a
brdy_done:
        call    io_delay
        pop     de
        pop     af
        ret
read_eight:
        ld      a,20h
        call    setup_transfer
        call    read_byte       ; Two dummy reads, each with readiness polling.
        call    read_byte
        ld      c,08h
read_loop:
        call    read_byte
        ld      (hl),a
        inc     hl
        dec     c
        jr      nz,read_loop
        jp      end_transfer
read_byte:
        ld      a,08h
        out     (16h),a
        call    wait_ready
        in      a,(17h)
        push    af
        call    transfer_ready
        pop     af
        ret
; Datasheet p53: pulse the BRDY mask, then poll BRDY or EOS.
; BUSY and buffer readiness are separate. All waits are bounded.
transfer_ready:
        push    bc
        push    de
        ld      b,10h
        ld      a,1Bh
        call    write_high
        ld      a,13h
        call    write_high
        ld      de,1000h
transfer_poll:
        in      a,(16h)
        and     0Ch
        jr      nz,transfer_ok
        dec     de
        ld      a,d
        or      e
        jr      nz,transfer_poll
        ld      a,(TIMED_OUT)
        or      02h
        ld      (TIMED_OUT),a
        scf
        jr      transfer_return
transfer_ok:
        or      a
transfer_return:
        pop     de
        pop     bc
        ret
status_eight:
        ld      c,08h
status_loop:
        in      a,(16h)
        ld      (hl),a
        inc     hl
        call    io_delay
        dec     c
        jr      nz,status_loop
        ret
write_high:
        push    af
        call    wait_ready
        ld      a,b
        out     (16h),a
        call    io_delay
        pop     af
        out     (17h),a
        jp      wait_ready
wait_ready:
        push    af
        push    de
        ld      de,1000h
wait_loop:
        in      a,(16h)
        and     80h
        jr      z,ready
        dec     de
        ld      a,d
        or      e
        jr      nz,wait_loop
        ld      a,(TIMED_OUT)
        or      01h
        ld      (TIMED_OUT),a
ready:
        call    io_delay
        pop     de
        pop     af
        ret
io_delay:
        push    bc
        ld      b,40h
spacing:
        djnz    spacing
        pop     bc
        ret
text:
        ld      a,(hl)
        inc     hl
        or      a
        ret     z
        call    put
        jr      text
put:
        push    hl
        push    bc
        push    de
        call    CHPUT
        di
        pop     de
        pop     bc
        pop     hl
        ret
print_eight:
        ld      b,08h
print_loop:
        ld      a,(hl)
        inc     hl
        call    hex_byte
        ld      a,20h
        call    put
        djnz    print_loop
        ret
hex_byte:
        push    af
        rrca
        rrca
        rrca
        rrca
        call    hex_digit
        pop     af
hex_digit:
        and     0Fh
        add     a,30h
        cp      3Ah
        jr      c,put
        add     a,07h
        jr      put
signature:      db "MKT5"
seed_ff:        db 0FFh,0FFh,0FFh,0FFh,0FFh,0FFh,0FFh,0FFh
seed_a:         db 0A1h,0A2h,0A3h,0A4h
seed_b:         db 0B1h,0B2h,0B3h,0B4h,0B5h,0B6h,0B7h,0B8h
seed_c:         db 0C1h,0C2h,0C3h,0C4h,0C5h,0C6h,0C7h,0C8h

title:          db "MAKOTO ADPCM TEST V5",0Dh,0Ah
                db "Cold power-on. No music.",0Dh,0Ah,00h
label_reset:    db 0Dh,0Ah,"STATUS BEFORE WRITES:",0Dh,0Ah,00h
label_open:     db 0Dh,0Ah,"STATUS AFTER 110H=00:",0Dh,0Ah,00h
label_base:     db 0Dh,0Ah,"BASELINE: EXPECT C1 C2 .. C8",0Dh,0Ah,00h
label_end:      db 0Dh,0Ah,"END=0000: WRITE A1 A2 A3 A4",0Dh,0Ah,00h
label_seed:     db 0Dh,0Ah,"RESEED: EXPECT B1 B2 .. B8",0Dh,0Ah,00h
label_limit:    db 0Dh,0Ah,"LIMIT=0000: READ 8 BYTES",0Dh,0Ah,00h
label_timeout:  db 0Dh,0Ah,"ERROR: 01=BUSY/ABSENT 02=BRDY: ",00h
label_checks:   db 0Dh,0Ah,"BASE/SEED OK, END WRITE COUNT: ",00h
footer:         db 0Dh,0Ah,0Dh,0Ah,"EE=SKIPPED. Please photo all results.",00h
        ds      8000h-$,0FFh
