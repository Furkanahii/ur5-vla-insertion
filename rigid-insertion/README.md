# UR5 rijit pim ve delik görevi

Bu ilk görev, UR5'e sabit bir pim tool'u bağlar ve betikli bir uzmanla yerleştirme yaptırır. Uzman delik pozunu simülatörden bilir. VLA henüz bu robotu kontrol etmiyor. Kamera, durum ve eylemler ortak `ur5_episode_v1` formatında kaydedilir.

[15 Kasım sonuç raporu](../RIGID-INSERTION-2026-11-15.md), yedi doğrulama/gösterim koşusunu, videoyu ve ölçüm grafiklerini içerir.

[Yeni açılı veri seti raporu](../ANGULAR-DATASET-2026-11-15.md), fiziksel başlangıç eğimi eklenen v2 sürümünü ve 12 senaryoluk sabit veri ayrımını içerir. Kamera bütün senaryolarda sabittir. Uzman, aşağıya inmeden önce hem konumu hem yönelimi düzeltir.

## Geometri ve kontrol

| Özellik | Değer |
| --- | --- |
| Pim çapı / silindirik şaft uzunluğu | 8 mm / 60 mm |
| Bağlantı adaptörü çapı / uzunluğu | 24 mm / 12 mm |
| Toplam tool kütlesi | Çelik yoğunluğu 7800 kg/m³ varsayımıyla yaklaşık 65,87 g |
| Bilek bağlantısından pim ucuna mesafe | 72 mm |
| Delik çapı / derinliği | 9,5 mm / 25 mm |
| Delik geometrisi | 128 dilimli açık halka; sabit üçgen ağ çarpıştırıcı |
| Etkin radyal boşluk | Yaklaşık 0,749 mm; mesh çokgeni hesaba katılır |
| Başlangıç yüksekliği / hedef giriş derinliği | Delik üstünde 25 mm / delik içine 20 mm |
| Kontrol / fizik | 20 Hz / 120 Hz |
| Motor kazançları | 800 / 60 |
| Yerçekimi | Açık; robot ve yeni tool kütlesi için tork telafisi uygulanır |

Bunlar simülasyon prototipinin ölçüleridir. Laboratuvar aparatıyla eşleştirilmiş veya optimize edilmiş dar toleranslı bir benchmark değildir.

Tool, UR5 `wrist_3_link` gövdesine sabit bir USD eklemiyle bağlı ayrı bir rijit gövdedir. Adaptör ve şaftın kütlesi, kütle merkezi ve atalet momentleri hesaplanıp uygulanır. Fizik motoru tool'u robotun sekizinci gövdesi olarak görür; altı hareketli eklem korunur.

Kullanılan yapılar: [USD sabit eklem](https://openusd.org/dev/api/class_usd_physics_fixed_joint.html), [USD kütle ve atalet özellikleri](https://openusd.org/dev/api/class_usd_physics_mass_a_p_i.html), [sabit üçgen ağ çarpışması](https://docs.omniverse.nvidia.com/kit/docs/omni_physics/107.0/dev_guide/rigid_bodies_articulations/collision.html).

## TCP ve koordinat tanımı

Kontrol edilen nokta, bilekten 72 mm uzaktaki pim ucudur. Jacobian'ın doğrusal kısmı bu ofsete taşınır. Eylemlerin XYZ ve rotasyon farkları robot taban çerçevesinde metre/radyan cinsindedir.

Pimin fiziksel gövdesinin +Z ekseni şaft boyunca aşağıya, TCP'nin +Z ekseni ise bileğe doğru yukarıya bakar. Böylece standart başlangıçta TCP yönelimi sıfıra yakın olur. Doğrudan aşağı bakan gövdeyi rotasyon vektörüyle kaydetmek, +180°/−180° sınırında yapay sıçrama oluşturuyordu; yeni TCP tanımı bunu önler. `tcp_offset_m_wxyz` çeviri ve yönelim ofsetini birlikte saklar.

Bu ilk sürümde taban ve dünya dönüşümü özdeştir, delik ekseni dünya Z eksenidir. Kod bu taban varsayımını doğrular. Eğik delik ve farklı robot taban pozları henüz bu sürümün testi değildir.

## Uzman ve başarı

Uzman önce delik üzerinde yatay hizalama yapar, sonra yavaşça aşağı iner ve hedefte bekler. Her bölüm 150 eylem / 151 gözlem, yani 7,5 saniyelik simülasyondur. Her eylemden önceki görüntü ve ölçülen durum, eylemden sonraki gözlemle zincirlenir.

Başarı, komut verilen hedefe göre hesaplanmaz. Ölçülen tool gövdesinden gerçek pim ucu ve şaft yönü çıkarılır. Bölümün son 10 kontrol adımında, yani en az 0,5 saniye boyunca:

- Ölçülen giriş derinliği en az 18 mm ve en fazla 25 mm olmalı.
- Pim ekseninin delik eksenine göre açısı 1° içinde kalmalı.
- Delik içindeki şaftın hem uç hem giriş düzlemi kesiti, yarıçap ve 0,1 mm ek payla deliğe sığmalı.

`task_success` yerleştirmenin sonucudur. `validation_passed` ise seçilen fizik kontrolünün beklenen sonucunu üretip üretmediğidir. Engelli bir testte `task_success=false` ve `validation_passed=true` olması doğrudur.

## Fizik kontrolleri

1. `aligned`: Açık delik ve hizalı pim; yerleştirme başarılı olmalı.
2. `rim`: Pim 8 mm yana kayık tutulur. Hedef yine 20 mm içeridedir, fakat fiziksel temas girişe engel olmalı.
3. `filled`: Delik ağzı ayrı bir sabit kapakla kapatılır. Hizalı komuta rağmen pim içeri girememeli.

İki engelli kontrolde, kaydedilen en büyük giriş derinliği 2 mm'nin altında kalmalı ve temas sinyali görülmeli. Böylece yalnızca pozdan başarı hesabını değil, mesh açıklığını ve çarpışmanın varlığını da sınarız.

Temas sensörü dünya çerçevesinde ham normal kuvvet vektörü verir. Bu veriler temasın varlığını incelemek için tutulur. Tam temas wrench'i, sürtünme bileşenleri ve fiziksel kuvvet doğruluğu henüz kalibre edilmedi; `wrench_validated=false`, `wrench=null` olarak kalır. Ham değerler kuvvet koşullu VLA eğitimi için doğrulanmış etiket sayılmaz.

## VALAR'da çalıştırma

Bu klasör, daha önce kurulan `../ur5-pilot/.runtime/` Isaac Lab imajını ve shader önbelleğini kullanır. Yeni indirme yapmaz. NVIDIA lisansını kabul ettiysen:

```bash
cd /scratch/HPC_USER/vla-hpc/rigid-insertion
export ACCEPT_EULA=Y
sbatch --partition=ai --account=ai --qos=ai --gres=gpu:tesla_t4:1 \
  --array=0-2%1 job.slurm validation
```

Dört sabit başlangıç ofseti (+3/−3 mm X ve Y):

```bash
sbatch --partition=ai --account=ai --qos=ai --gres=gpu:tesla_t4:1 \
  --array=0-3%1 job.slurm demonstrations
```

`%1` aynı diziden en fazla bir işi çalıştırır. Tek hizalı kontrol için `job.slurm aligned` kullanılır. Betik kaynakları her iş için kopyalar; çalışma sırasında yapılan kod değişikliği o işe yansımaz.

## Çıktılar ve doğrulama

`runs/IS_NO_ADIM/` altında `config.json`, `summary.json`, `episode.json`, `transitions.jsonl`, ayrıntılı `steps.jsonl`, 151 PNG, `motion.gif`, kaynak SHA-256 ve GPU bilgisi bulunur. Bu ilk fizik ve gösterim kontrolleri henüz bir eğitim/test veri seti değildir; eğitim uygunluğu kapalıdır.

Manifest ile üretilen yeni bölümlerde bu ayrım açıkça yapılır: başarılı eğitim bölümleri eğitim için uygundur; doğrulama/test bölümleri veri setine dahil olup eğitim uygunlukları kapalıdır. Eski fizik kontrolleri ve manifest dışı denemeler eğitim verisine alınmaz.

12 sabit konum/açı senaryosunu üretmek için:

```bash
sbatch --partition=ai --account=ai --qos=ai --gres=gpu:tesla_t4:1 \
  --export=ALL,ACCEPT_EULA=Y --array=0-11%1 job.slurm dataset
```

`pilot_manifest.json`, 8 eğitim, 2 doğrulama ve 2 test başlangıcını sabitler. X/Y başlangıç eğimi bileşenleri, derece cinsinden taban çerçevesi rotasyon vektörüdür; Euler açıları değildir. Her bölüm başlamadan önce robot bu eğime fiziksel olarak hazırlanır. İlk görüntü ve durum, hazırlık tamamlandıktan sonra alınır. Tek ön deneme için `job.slurm dataset 6` kullanılır; bütün veri setine ayrıca katılmaz.

```bash
PYTHONPATH=../ur5-pilot python3 -m unittest discover -s . -p 'test_*.py' -v
PYTHONPATH=../ur5-pilot python3 check_insertion.py runs/IS_NO_ADIM
```

## Sonraki aşamalar

Başlangıç ofsetleri/açıları, sabit eğitim/doğrulama/test manifesti ve [RLDS/OpenVLA veri adaptörü](../data-adapter/README.md) ilk pilot düzeyinde tamamlandı. Sonraki aşamalar daha çok gösterim, kamera/aydınlatma çeşitliliği, ilk öğrenme denemesi ve kapalı çevrim UR5 değerlendirmesidir. Yumuşak delik testi ayrı bir yapılabilirlik adımıdır; bu rijit görevin başarısından çıkarılamaz.
