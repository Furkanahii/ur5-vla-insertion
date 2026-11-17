# İkinci hafta teslimi

Bu paket, proje belgesinin 1–2. hafta teknik ödevini kapatır. Amaç, UR5 simülasyonu ile hazır VLA örneğinin ayrı ayrı çalıştığını göstermek ve ortak veri arayüzünü belgelemektir. UR5 üzerinde öğrenilmiş insertion politikası bu haftanın teslimi değildir.

[Özgün proje planı](project-plan.docx), kullanıcının verdiği dosyanın değişmemiş kopyasıdır. Dosya SHA-256: `71cf65cbed7600d4f35a243e4d1131cc1d1acecf333b3a9cad9a34c52a241967`.

## Gereklilik ve kanıt

| Belgedeki 1–2. hafta gerekliliği | Doğrulanmış çıktı | Sonuç |
| --- | --- | --- |
| Isaac Sim/Lab kurulumu ve UR5 varlığı | Isaac Lab 2.3.0 / Sim 5.1.0 SIF; sabit tabanlı altı eklemli UR5 | Geçti |
| Tool ve sanal kamera yapılandırması | `rigid-insertion/runs/2028002_0/`: sabit kütleli pim, pim ucu TCP, kamera kalibrasyonu ve fiziksel giriş | Geçti |
| Basit Kartezyen hareket | `ur5-pilot/runs/2025430/`: yerçekimi açıkken X yönünde 30 mm | Geçti |
| Kamera videosu ve poz/eylem kaydı | Aşağıdaki MP4, 51 kaynak görüntü, 50 eylem, `steps.jsonl`, `transitions.jsonl`, `episode.json` | Geçti |
| Resmî OpenVLA-OFT örneği | `runs/1952021/`: LIBERO-10, 10 kapalı çevrim bölüm ve 10 video; 10 başarı | Geçti; görev başına bir ilk deneme |
| GPU ve yazılım kapasitesini kaydet | A40 üzerinde VLA, T4 üzerinde UR5; sürümler ve paket kaydı aşağıda | Geçti |
| Ortak durum/eylem/bölüm şeması | Metre/radyan, taban çerçevesi, wxyz, 7D eylem / 8D proprio ve zaman sırası belgeli | Teknik doğrulama geçti |
| Şemayı iki öğrencinin birlikte gözden geçirmesi | Aşağıdaki kısa ekip incelemesi | Öğrenciler tarafından yapılacak; otomatik kontrol bunu onaylayamaz |
| Tek paylaşılan sürümlü kaynak deposu | VALAR üzerindeki özel SSH Git deposu ve ikinci hafta etiketi | Kurulum/handoff kaydı: `source-repository.json` |

## Önce bunları aç

1. [UR5 hareket videosu](ur5-motion.mp4): ilk gözlem dahil 51 kare, 20 fps, 2,55 saniye. 50 kontrol eylemi 2,5 saniyedir.
2. [Ayrı OpenVLA örnek videosu](../../audit/2026-11-15/libero-demo.mp4): hazır modelin LIBERO robotunu görüntü ve talimatla kontrol etmesi.
3. [Ortak şema](../../ur5-pilot/EPISODE_SCHEMA.md): iki tarafın aynı veriyi nasıl okuyacağı.
4. [Sayısal doğrulama sonucu](verification.json) ve [ortam kontrolü](environment.json).

UR5 hareket pilotunda kontrol noktası bilektir. Sabit pim bulunan ayrı sahnede kontrol noktası pim ucudur; metadata bu dönüşümü saklar. İkisi aynı TCP varsayımıyla karıştırılmaz.

Hareket kaydında en büyük örneklenmiş Z hedef hatası 0,1795 mm; delta eylem yeniden oynatmasında bütün örneklerdeki en büyük konum farkı yaklaşık 0,685 mikrometre. İlk kayıtta görülen yaklaşık 30,7 mm Z sarkması ağırlık telafisiyle giderildi. Ham eski tanı kayıtları tarihçe olarak korunur.

Son byte karşılaştırmasında Mac/Linux üzerinde yeniden türetilen iki geçiş dosyasında en fazla `4,44e-16` proprio yuvarlama farkı görüldü. Teslimde VALAR dışa aktarımı ortak kopya olarak alındı; eski Mac türevleri `.audit/week2-pre-canonical` altında korundu. Ham `steps.jsonl` ve görüntüler değiştirilmedi. [Karşılaştırma kaydı](cross-platform.json) ayrıntıları saklar.

## Doğrulanmış ortam

| İş | Kullanılan kaynak | Not |
| --- | --- | --- |
| OpenVLA-OFT + LIBERO | A40, 46.068 MiB VRAM, 4 CPU, 32 GiB RAM isteği | PyTorch 2.2.0 + CUDA 12.1; BF16 preflight geçti |
| UR5 kamera ve hareket | Tesla T4, 4 CPU, 32 GiB RAM isteği | 60 Hz fizik / 20 Hz kontrol; yerçekimi açık |
| Rijit tool sahnesi | Tesla T4 | 120 Hz fizik / 20 Hz kontrol; sabit pim |
| Giriş düğümü | Rocky Linux 8.9, glibc 2.28 | Isaac için Singularity 4.3.2 kullanılır |

Bu tablo kullanılan kaynakları kaydeder; minimum bellek ihtiyacı ölçümü değildir. [Paket listesi](packages-recorded.txt), çalışan LIBERO kaydından alınmıştır. Yerel scratch yollarını içerdiği için doğrudan başka bilgisayarda kurulacak bir requirements dosyası değildir; kurulum için `setup.sh` ve constraints dosyaları kullanılır.

Kaynak sürümleri: OpenVLA-OFT `e4287e94541f459edc4feabc4e181f537cd569a8`, LIBERO `8f1084e3132a39270c3a13ebe37270a43ece2a01`. Çalıştırılan modelin Hugging Face revision'ı `95220f9a3421a7ff12d4218e73d09ade830fa9a3` olarak kayıtlıdır. Mevcut önbellek bu sürümle denetlenir. Standart değerlendirme komutundaki model adı Hugging Face `main` dalını kullanır; ileride yeni ağırlık yayımlanırsa bu eski teslimin sürümüyle aynı sayılmamalıdır.

## Birlikte yapılacak kısa inceleme

Bu teknik kontroller tamamlandı. Furkan ve Maho'nun ortak arayüzü gözden geçirmesi, belgenin ayrıca istediği ekip çalışmasıdır. Bir örnek bölümde şu beş madde birlikte okunur:

- Eylemden önceki görüntü ile ölçülen durum aynı adıma ait mi?
- Konum metre, yönelim farkı radyan; çerçeve robot tabanı mı?
- `proprio` 8, `action` 7 sayı mı; sabit tool kanalları sıfır mı?
- TCP bilek mi, pim ucu mu; metadata doğru okunuyor mu?
- Delik gerçek pozu ve uzman hedefi model girdisinin dışında mı?

İnceleme yapıldığında `ISSUES.md` içindeki `TEAM-01` maddesine tarih ve iki öğrencinin notu eklenir. Bu onay yapılmış gibi işaretlenmedi. Sonraki büyük veri üretimi bu ortak incelemeden sonra ele alınır.

## Kaynağı paylaşma ve yeniden denetleme

Koç VPN/SSH erişimi olan yetkili ekip üyesi kaynakları ayrı bir klasöre alabilir:

```bash
git clone --upload-pack=/scratch/HPC_USER/vla-hpc/git-tools/upload-pack.sh \
  HPC_USER@login.valar.ku.edu.tr:/scratch/HPC_USER/vla-hpc/shared-source.git vla-hpc-source
cd vla-hpc-source
git checkout week2-2026-11-15
```

VALAR'ın Git modülü SSH komutlarında kendiliğinden açılmadığı için `--upload-pack` kullanılır. İleride bu klondan kod göndermek için bir defa şu ayar eklenir:

```bash
git config remote.origin.receivepack /scratch/HPC_USER/vla-hpc/git-tools/receive-pack.sh
git config remote.origin.uploadpack /scratch/HPC_USER/vla-hpc/git-tools/upload-pack.sh
```

Repo kaynakları, raporları ve küçük teslim dosyalarını taşır. `.runtime`, büyük model dosyaları, ham `runs` ve TFDS çıktıları Git'e eklenmez. Tam çalışan veri ve ortam aynı hesabın `/scratch/HPC_USER/vla-hpc` klasöründe ve Furkan'ın Mac kopyasında saklanır. Kaynak klonu tek başına ham deney kayıtlarını içermez.

Mevcut VALAR çalışma alanında yeni GPU işi göndermeden denetle:

```bash
cd /scratch/HPC_USER/vla-hpc
module load git/2.9.5 singularity/4.3.2
.runtime/env/bin/python verify_environment.py
.runtime/env/bin/python verify_week2.py
bash status.sh
```

İkinci komut mevcut dosyaları, paket uyumunu, SIF tablosunu, model parça indekslerini ve kaynak sürümlerini denetler. Üçüncü komut 10 LIBERO videosunu ve UR5 MP4'ünü baştan sona çözer; görüntü/eylem kayıtlarını ve tekrar oynatmayı kontrol eder. Mevcut ek pilotun veri checksum'ları da karşılaştırılır. Kod veya ham kayıt bilerek değiştirilirse eski kanıt geçersiz olabilir; doğrulayıcı bunu hata olarak gösterir.

## İkinci haftanın dışında, korunmuş tamamlanmış pilotlar

Rijit sahne, 12 başlangıçlı gösterim pilotu ve RLDS/OpenVLA veri dönüşümü de daha önce tamamlandı. [Başlatılan işler envanteri](../../STARTED_WORK.md) bunları sınırlarıyla kaydeder. Küçük pilotta test normalizasyonunun sınırına takılan değerler vardır; bu set büyük eğitim veya genelleme sonucu olarak kullanılmaz. UR5 fine-tuning, öğrenilmiş kapalı çevrim politika, basit görsel baseline ve yumuşak temas deneyi henüz başlatılmadı. Bu denetim yeni araştırma işi veya eğitim başlatmaz.
