; Makoto RAM transfer comparison V4. Original synthetic diagnostic.
; Compare V3 against the reset/ready sequence used by Grauw's Makoto driver.
; Reference: https://hg.sr.ht/~grauw/vgmplay-msx (src/drivers/Makoto.asm).
; No music; only ports 16h/17h. IRQ sources masked before BIOS display calls.
; Build: tniasm compat.asm Contrib/makoto-ram-transfer-test.asm output.rom
%symfile "derived/makoto-ram-transfer-test.sym"
        org     4000h
        db      "AB"
        dw      boot,0000h,0000h,0000h,0000h,0000h,0000h
RESULT          equ     0C100h
TIMED_OUT       equ     RESULT+04h
RESET_STATUS    equ     RESULT+10h
OPEN_STATUS     equ     RESULT+18h
ROW_A           equ     RESULT+20h
ROW_B           equ     RESULT+28h
ROW_C           equ     RESULT+30h
ROW_D           equ     RESULT+38h
END_ADDRESS     equ     RESULT+40h
LIMIT_ADDRESS   equ     RESULT+42h
TRANSFER_MODE   equ     RESULT+44h
WRITE_COUNT     equ     RESULT+45h
ERRORS          equ     RESULT+48h
CHGMOD          equ     005Fh
CHPUT           equ     00A2h

boot:
        di
        ld      sp,0F300h
        ld      a,(002Dh)
        cp      03h
        jr      nz,z80_ready
        ld      a,80h
        call    0180h
z80_ready:
        di
        ld      hl,RESULT
        ld      de,RESULT+01h
        ld      bc,004Fh
        ld      (hl),00h
        ldir
        ld      hl,RESET_STATUS
        call    status_eight
        ld      a,(RESET_STATUS)
        cp      0FFh
        jp      z,absent
        ld      b,10h
        xor     a
        call    write_high
        ld      hl,OPEN_STATUS
        call    status_eight
        call    full_range
        ; A: unchanged V3 control experiment.
        ld      hl,seed_c
        ld      c,08h
        call    write_block
        ld      hl,ROW_A
        call    read_eight
        ld      a,(TIMED_OUT)
        ld      (ERRORS),a
        xor     a
        ld      (TIMED_OUT),a
        ; B: reset/ready writer, unchanged V3 reader.
        call    reference_write
        ld      hl,ROW_B
        call    read_eight
        ld      a,(TIMED_OUT)
        ld      (ERRORS+01h),a
        xor     a
        ld      (TIMED_OUT),a
        ; C: reset/ready writer, explicit-reset reader with flag handshakes.
        call    reference_write
        ld      hl,ROW_C
        call    reset_read
        ld      a,(TIMED_OUT)
        ld      (ERRORS+02h),a
        xor     a
        ld      (TIMED_OUT),a
        ; D: same reset setup, stream reads without reselecting registers.
        call    reference_write
        ld      hl,ROW_D
        call    stream_read
        ld      a,(TIMED_OUT)
        ld      (ERRORS+03h),a
        ld      b,10h
        ld      a,1Fh
        call    write_high
        jr      display
absent:
        ld      a,01h
        ld      (TIMED_OUT),a
        ld      (ERRORS),a
        ld      (ERRORS+01h),a
        ld      (ERRORS+02h),a
        ld      (ERRORS+03h),a
display:
        ld      hl,signature
        ld      de,RESULT
        ld      bc,0004h
        ldir
        xor     a
        ld      (0F3DBh),a
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
        ld      hl,label_initial
        call    text
        ld      hl,RESET_STATUS
        call    print_eight
        ld      hl,label_unmask
        call    text
        ld      hl,OPEN_STATUS
        call    print_eight
        ld      hl,label_a
        call    text
        ld      hl,ROW_A
        call    print_eight
        ld      hl,label_b
        call    text
        ld      hl,ROW_B
        call    print_eight
        ld      hl,label_c
        call    text
        ld      hl,ROW_C
        call    print_eight
        ld      hl,label_d
        call    text
        ld      hl,ROW_D
        call    print_eight
        ld      hl,label_errors
        call    text
        ld      hl,ERRORS
        ld      b,04h
        call    print_loop
        ld      hl,footer
        call    text
idle:
        ei
        halt
        jr      idle

; Configure addresses, then explicitly reset the engine before selecting mode.
configure_reset:
        call    setup_transfer
        push    bc
        ld      b,00h
        ld      a,01h
        call    write_high
        ld      a,(TRANSFER_MODE)
        call    write_high
        pop     bc
        ret
reference_write:
        ld      hl,seed_c
        ld      c,08h
        ld      a,60h
        call    configure_reset
        ld      b,10h
        ld      a,14h          ; VGMPlay exposes BRDY while masking EOS.
        call    write_high
reference_loop:
        call    wait_brdy
        ld      b,08h
        ld      a,(hl)
        inc     hl
        call    write_high
        ld      b,10h
        ld      a,0F0h         ; Reset flags, retain the current mask.
        call    write_high
        dec     c
        jr      nz,reference_loop
        call    wait_brdy      ; Let the final transfer complete before stopping.
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
reset_read:
        ld      a,20h
        call    configure_reset
        call    read_byte
        call    read_byte
        ld      c,08h
        jp      read_loop
stream_read:
        ld      a,20h
        call    configure_reset
        ld      a,08h
        out     (16h),a
        call    wait_ready
        call    stream_byte
        call    stream_byte
        ld      c,08h
stream_loop:
        call    stream_byte
        ld      (hl),a
        inc     hl
        dec     c
        jr      nz,stream_loop
        jp      end_transfer
stream_byte:
        in      a,(17h)
        ; Deliberately leave register 108h selected throughout the stream.
        ; The fixed delay is also a control against stale BRDY flag timing.
        call    io_delay
        call    wait_brdy
        ret

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
write_loop:
        ld      b,08h
        ld      a,(hl)
        inc     hl
        call    write_high
        ld      a,(WRITE_COUNT)
        inc     a
        ld      (WRITE_COUNT),a
        call    transfer_ready
        jr      c,write_done
        bit     2,a             ; EOS: do not submit bytes beyond the end.
        jr      nz,write_done
        dec     c
        jr      nz,write_loop
write_done:
        jp      end_transfer
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
signature:      db "MKT4"
seed_c:         db 0C1h,0C2h,0C3h,0C4h,0C5h,0C6h,0C7h,0C8h
title:          db "MAKOTO RAM COMPARISON V4",0Dh,0Ah
                db "Each RAM row expects C1 C2 .. C8",0Dh,0Ah,00h
label_initial:  db 0Dh,0Ah,"STATUS BEFORE WRITES",0Dh,0Ah,00h
label_unmask:   db 0Dh,0Ah,"STATUS AFTER UNMASK",0Dh,0Ah,00h
label_a:        db 0Dh,0Ah,"A: V3 WRITE / V3 READ",0Dh,0Ah,00h
label_b:        db 0Dh,0Ah,"B: RESET WRITE / V3 READ",0Dh,0Ah,00h
label_c:        db 0Dh,0Ah,"C: RESET WRITE / RESET READ",0Dh,0Ah,00h
label_d:        db 0Dh,0Ah,"D: RESET WRITE / STREAM READ",0Dh,0Ah,00h
label_errors:   db 0Dh,0Ah,"ERRORS A B C D (00=OK): ",00h
footer:         db 0Dh,0Ah,0Dh,0Ah,"Cold boot. Please photo all results.",00h
        ds      8000h-$,0FFh
