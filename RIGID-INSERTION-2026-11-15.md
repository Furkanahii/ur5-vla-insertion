# UR5 ilk rijit yerleştirme sahnesi ve fizik kontrolleri

UR5'e sabit pim tool'u, gerçekten açık bir rijit delik, temas kaydı ve ölçülen pim pozundan başarı kontrolü eklendi. Delik pozunu bilen betikli uzman bir hizalı koşuda ve dört küçük başlangıç ofsetinde yerleştirmeyi tamamladı. İki engelli kontrol de beklenen biçimde girişe izin vermedi. Robotu henüz VLA yönetmiyor.

[7,5 saniyelik yerleştirme videosu](audit/2026-11-15/rigid-insertion/aligned-insertion.mp4) · [Sahne karşılaştırması](audit/2026-11-15/rigid-insertion/scene-comparison.png) · [Ölçüm grafikleri](audit/2026-11-15/rigid-insertion/validation.png)

## Sonuçlar

| Koşul | İş | Beklenen ve ölçülen sonuç |
| --- | --- | --- |
| Hizalı açık delik | `2025864_0` | Başarılı; son giriş derinliği 20,000 mm |
| Pim 8 mm yana kayık | `2025864_1` | Kenarda fiziksel olarak engellendi; yerleştirme başarısız |
| Delik ağzı kapalı | `2025864_2` | Kapakta fiziksel olarak engellendi; yerleştirme başarısız |
| Delik X yönünde +3 mm | `2025865_0` | Uzman hizaladı ve yerleştirdi |
| Delik X yönünde −3 mm | `2025865_1` | Uzman hizaladı ve yerleştirdi |
| Delik Y yönünde +3 mm | `2025865_2` | Uzman hizaladı ve yerleştirdi |
| Delik Y yönünde −3 mm | `2025865_3` | Uzman hizaladı ve yerleştirdi |

Yedi işin tamamı `COMPLETED`, çıkış kodu 0. Buradaki **7/7 fizik doğrulaması**, beş başarılı yerleştirme ve iki beklenen engellenmeden oluşur; yedi başarılı yerleştirme anlamına gelmez. Bu, genel bir başarı oranı ölçümü değildir.

Başarılı beş koşunun son giriş derinliği yaklaşık 19,9994–19,9998 mm; son yanal hatası yaklaşık 0,0011–0,0018 mm. İki engelli kontrolde pim ucu giriş düzleminin altına geçmedi. Hedef 20 mm içeride kaldığı halde ölçülen pim hareketinin durması ve temas sinyalinin oluşması, çarpışmanın gerçekten devrede olduğunu gösterdi.

[Sayısal sonuçlar](audit/2026-11-15/rigid-insertion/results.json) · [Slurm kayıtları](audit/2026-11-15/rigid-insertion/jobs.psv)

## Kurulan sahne

- Pim çapı 8 mm, silindirik şaft 60 mm; adaptör 24 mm çap ve 12 mm uzunlukta.
- Çelik yoğunluğu varsayımıyla toplam tool kütlesi 65,87 g. Kütle merkezi ve ataletleri tanımlandı.
- Tool, UR5 bileğine sabit bir eklemle bağlı ayrı rijit gövde. Fizik motoru sekiz gövde ve altı hareketli eklem görüyor.
- Delik çapı 9,5 mm, derinliği 25 mm. Halka 128 dilimli sabit üçgen ağdır; ortası çarpışma geometrisinde de açıktır.
- Robotun yerçekimi açık, tool kütlesi de ağırlık telafisine dahil. Kontrol 20 Hz, fizik 120 Hz; motor kazançları 800/60.
- Tek dış RGB kamera 640×480 kayıt alıyor. Kalibrasyon ve dünya/taban/tool dönüşümleri metadata'da.

Geometri ilk simülasyon varsayımıdır; laboratuvar aparatıyla eşleştirilmedi. Delik, yaklaşık 0,749 mm etkin radyal boşluk bırakan kolay bir başlangıçtır.

## Başarı ve veri kontrolü

Başarı için hedef koordinatına bakılmıyor. Ölçülen pim ucu ve şaft yönünden giriş derinliği, yanal uzaklık ve giriş düzlemindeki şaft kesiti hesaplanıyor. Son 10 kontrol adımında en az 18 mm giriş, 1° açı sınırı ve şaftın boşluğa sığması gerekiyor. Böylece bölümün ortasında oluşup sonradan kaybolan bir durum başarı sayılmıyor.

TCP, bilekten 72 mm uzaktaki pim ucuna taşındı; Jacobian da bu mesafe için düzeltildi. Pim gövdesi aşağı bakarken TCP +Z ekseni bileğe doğru yukarı bakıyor. Bu tanım, gözlem yöneliminin +180°/−180° sınırında yapay sıçramasını önlüyor. İlk taslaktaki 6,283 rad sıçrama, yeni kayıtların tamamında en fazla 0,001315 rad oldu; başarılı yerleştirmelerde en fazla yaklaşık 0,000175 rad.

Yedi bölümde toplam **1050 eylem/geçiş ve 1057 PNG gözlem** var. Her bölüm 150 eylem ve 151 gözlem içeriyor. Bütün PNG'ler Mac'te PIL ile açılıp doğrulandı. Ortak şema, zaman zinciri ve ölçülen pozlardan başarı hesabı ayrıca simülatör dışında kontrol edildi. Yedi iş aynı kaynak SHA-256 kümesini kullandı. Video 150 kare, 640×480 H.264 ve 7,5 saniye olarak `ffprobe` ile doğrulandı.

Yerelde 14 ortak arayüz testi ve 7 geometri/TCP testi geçti. Yeni geometri/TCP testleri VALAR'da da geçti. Bunlar açık delik topolojisini, farklı pozların başarı hesabını, tool ataleti, eylem sınırları ve yönelim temsilini kapsıyor.

Görev kimliği `ur5_rigid_peg_insertion_v1`, gözlem/eylem şeması `ur5_episode_v1`. Hedef ve gerçek delik pozu değerlendirme bölümünde saklanıyor; model girdisi fonksiyonu bunları seçmiyor. Mevcut bölümler ilk doğrulama örnekleridir; eğitim uygunluğu kapalı tutuldu.

## Temas verisinin sınırı

Sensör, ham normal temas kuvvetini dünya çerçevesinde kaydediyor. Bu aşamada temasın varlığı fiziksel engellenmeyle birlikte kontrol edildi. Tam wrench, sürtünme kuvvetleri veya fiziksel kuvvet doğruluğu kalibre edilmedi. `wrench_validated=false` ve `wrench=null` korunuyor; bu kayıtlar kuvvet koşullu VLA için doğrulanmış kuvvet etiketleri değildir.

## Kullanım ve sıradaki işler

[Çalıştırma ve geometri rehberi](rigid-insertion/README.md), üç kontrolü ve dört ofsetli gösterimi yeniden üretir. [Proje yol haritası](PROJECT_ROADMAP.md) güncellendi.

Sonraki aşamalar: başlangıç açılarının çeşitlendirilmesi, ayrı eğitim/doğrulama/test senaryoları, daha fazla kamera/başlangıç varyasyonu, RLDS/OpenVLA adaptörü ve ilk küçük fine-tuning. Yumuşak delik için belgedeki ayrı yapılabilirlik testi de yapılacak. Bugünkü sonuçlar tek geometri, tek kamera, sabit dört yanal ofset ve sıfır başlangıç açı hatasıyla sınırlıdır.
