# Tekrar üretim

## Üç ayrı kontrol seviyesi

1. **CPU testleri:** GitHub klonunda README komutlarıyla çalışır. GPU, model ve ham veri gerektirmez.
2. **Küçük UR5 örneği:** [Handoff rehberi](../deliverables/handoff-2026-11-16/README.md) ve ZIP kullanılır. Aynı SIF/container, NVIDIA varlık erişimi ve Slurm GPU gerekir.
3. **Tüm tarihsel kayıtların denetimi:** `verify_week2.py`, `verify_environment.py` ve ayrıntılı checksum kontrolleri tam yerel/HPC çalışma alanındaki ham `runs/`, `.runtime/` ve `data-adapter/builds/` çıktılarıyla çalışır. Yalnız GitHub klonu bu büyük dosyaları içermez.

## Doğrulanmış referans

- Isaac Lab 2.3.0 / Isaac Sim 5.1.0 / Singularity 4.3.2.
- UR5 referans işleri: Tesla T4; 4 CPU, 32 GiB RAM isteği.
- OpenVLA-OFT / LIBERO referansı: A40; aynı UR5 görevine aktarılmış politika değildir.
- Sabit container digest'i ve kaynak sürümleri teslim rehberinde kayıtlıdır.
- A40 için UR5 başlatma komutu belgelenmiştir; bu cihazda yeni UR5 koşusu yapılmış sayılmaz. Isaac Sim 6.2.0 uyumluluğu test edilmedi.

## Tam veriyi nerede tutuyoruz?

Model ağırlıkları, yaklaşık 8,34 GB SIF, Python ortamları, ham episode görüntüleri ve TFDS çıktıları mevcut yetkili yerel/HPC çalışma alanında kalır. GitHub kaynak ve küçük kanıt deposudur. Bu dosyalar üçüncü taraf depolara otomatik yüklenmez.

Makine/kullanıcı yolları paylaşım kopyasında yer tutucularla değiştirilmiştir. `HPC_USER`, `LOCAL_USER` veya `KULLANICI` görülen örnekler kendi hesabına göre düzenlenir. Shell komutlarında çalıştırma öncesi gerçek yol kullanılmalıdır.
