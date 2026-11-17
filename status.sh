#!/bin/bash
# Run this script on the VALAR login node.
set -euo pipefail
cd -- "$(dirname -- "$0")"

printf 'VALAR sunucu saati: '
date '+%Y-%m-%d %H:%M:%S %Z'
printf '\nSon 14 gündeki proje işleri (ID | Ad | Durum | Süre | Çıkış | Başlangıç | Bitiş)\n'
sacct -X -n -P -u "$USER" --starttime="${VLA_STATUS_SINCE:-now-14days}" \
    --name=vla-libero,ur5-pilot,ur5-diag,ur5-comp,ur5-insertion,ur5-data,ur5-data-probe \
    --format=JobID,JobName,State,Elapsed,ExitCode,Start,End
printf '\nHesabın şu an kuyruktaki işleri ve bekleme nedenleri\n'
squeue -u "$USER" -o '%.18i %.20j %.12T %.12M %R'
printf '\nBu klasördeki LIBERO ve UR5 sonuç özetleri\n'
for results in runs ur5-pilot/runs rigid-insertion/runs; do
    if [[ -d "$results" ]]; then
        find "$results" -maxdepth 2 -type f -name summary.json -print
    fi
done
printf '\nVeri seti ve OpenVLA adaptörü doğrulama çıktıları\n'
if [[ -d data-adapter/builds ]]; then
    find data-adapter/builds -maxdepth 2 -type f \( -name build_summary.json -o -name adapter_verification.json \) -print
fi
printf '\nDiskteki indirme alanları\n'
for path in .runtime/huggingface .runtime/wheelhouse ur5-pilot/.runtime; do
    if [[ -d "$path" ]]; then du -sh "$path"; fi
done
printf '\nRUNNING çalışıyor, PENDING sırada, COMPLETED tamamlandı.\n'
printf 'FAILED, TIMEOUT veya CANCELLED varsa ilgili iş günlüğünü inceleyin.\n'
printf 'Dependency önceki işin bitmesini, Resources veya Priority kaynak sırasını bekler.\n'
printf 'Disk boyutları geçici dosyaları da içerir. Tamamlanma yüzdesi değildir.\n'
