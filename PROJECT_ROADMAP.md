# UR5 yerleştirme projesinin çalışma planı

Amaç, UR5'in kamera görüntüsü ve dil talimatından eylem üreterek rijit bir pimi rijit bir deliğe yerleştirmesidir. Başlangıç belgesinin ana teslimi, tekrar üretilebilir bir simülasyon görevi, gösterim veri seti, OpenVLA-OFT ile kapalı çevrim denemeler ve nicel karşılaştırmadır. Yumuşak delik için ayrı bir yapılabilirlik raporu gerekir. Başarılı bir yumuşak delik VLA'sı ve kuvvet koşullu model ek hedeflerdir.

Kaynak: `VLA_Peg_Insertion_Student_Project_Plan_Isaac_Lab_UR5.docx`, dört sayfa; özellikle bölüm 3, 5, 6 ve 9. Takvim haftalarını otomatik geçti saymak yerine her aşamanın aşağıdaki ölçülebilir çıktısını doğruluyoruz.

## Mevcut durum ve sıra

1–2. haftanın teknik teslimi tamamlandı; 3–4. haftanın rijit görev/veri pilotları hazır. Yumuşak delik deneyi ve ortak ekip incelemesi açık. [İkinci hafta teslimi](deliverables/week2/README.md) bu haftanın teknik kontrolüdür. Daha önce tamamlanan ileri pilotlar korunur; yeni aşamaya geçmeden ekip şema incelemesi yapılacaktır.

| Aşama | Tamamlanma ölçütü | Durum |
| --- | --- | --- |
| GPU ve VLA örneği | OpenVLA-OFT ile LIBERO kapalı çevrim değerlendirmesi, video ve paket sürümleri | Tamam: 10 görevde birer deneme, 10 başarı |
| UR5 kamera ve hareket | Aynı anda görüntü ve poz kaydı, hareket takibi ve yeniden oynatma | Tamam: ilk tanı koşulları ve yerçekimi kapalı referans |
| Yerçekimi açık kontrol | Isınmada sarkmayı ve hareket sırasında Z hatasını azalt, kaydı tekrar oynat | Tamam: telafili kayıt ve delta eylem yeniden oynatma geçti; en büyük Z hatası 0,18 mm |
| Ortak veri arayüzü | Gözlem → eylem → yeni gözlem; birim, TCP, çerçeve, maskeleme tanımlı | Tamam: 14 CPU testi, iki GPU bölümünde 50 eylem / 51 gözlem doğrulandı |
| Paylaşılan kaynak deposu | Öğrencilerin kullandığı ortak Git deposu ve sürüm kaydı | Bağımsız yerel Git ve özel VALAR bare repo hazır; ikinci hafta etiketi ve klonlama talimatı teslimde. Her GPU işinin kaynak SHA-256 kaydı korunur |
| Rijit pim–delik görevi | Sabitlenmiş pim, fiziksel delik geometrisi, kamera, ölçülen TCP, temas ve başarı kontrolü | İlk sürüm tamam: hizalı giriş, kenarda engellenme ve kapalı delik kontrolleri geçti |
| Uzman gösterimleri | Ayrık başlangıç konum/açı senaryolarında tekrarlanabilir betikli uzman ve bölüm kayıtları | İlk pilot tamam: 8 eğitim, 2 doğrulama, 2 test senaryosu; 12/12 uzman başarısı, 1–2,69° fiziksel başlangıç eğimi |
| OpenVLA veri adaptörü | Eğitim verisi dönüşümü, yalnızca eğitimden normalizasyon, bölüm içi eylem chunk'ları | Tamam: RLDS/TFDS; 1.812 görüntü ve 1.800 eylem eşleşti; 1.144 eğitim / 286 doğrulama chunk'ı ve gerçek processor/collator batch'i geçti |
| İlk fine-tuning | Sabit sürüm ve tohumla küçük deneme; kaydedilmiş checkpoint ve kapalı çevrim UR5 rollout | Veri adaptörü geçti; eğitim girişinin UR5 sınıfına bağlanması ve kapalı çevrim politika uygulaması sırada |
| Karşılaştırmalı değerlendirme | Aynı saklı test durumlarında uzman, basit baseline ve VLA | Eğitimden önce test manifesti sabitlenecek |
| Rijit–yumuşak temas yapılabilirliği | Gerçek delik deformasyonu, sayısal kararlılık, erişilebiliyorsa doğrulanmış kuvvet–yer değiştirme | Belgedeki 4. hafta kontrolü; büyük eğitimden önce ayrı küçük deney |
| Fiziksel UR5 | Gerçek robot/fixture/kamera özellikleri ve kalibrasyon doğrulandı | Sonraki laboratuvar aşaması; robot erişimi gerekli |

## Şu an uygulanan teknik adım

Yerçekimini açık tutup PhysX'in hesapladığı ağırlık telafisi torklarını motor komutuna ekliyoruz. Kazançlar 800/60 ve kontrol 20 Hz. Hareket pilotunda fizik 60 Hz, yeni rijit insertion görevinde 120 Hz kullanılıyor. Ağırlık telafisi tork komutları temas kuvveti verisi gibi etiketlenmiyor.

Yeni veri formatının ayrıntıları [ortak şema rehberinde](ur5-pilot/EPISODE_SCHEMA.md). Hareket pilotu verisi, insertion eğitimi için uygun değil olarak işaretlenir. Böylece aynı dosya biçimini test ederken modele henüz gerçekleşmemiş bir insertion başarısı öğretmeyiz.

[Açılı veri seti ve adaptör sonucu](ANGULAR-DATASET-2026-11-15.md) yeni aşamayı kaydeder. Kamera sabit, başlangıçlar ve veri bölümleri manifestte sabittir. Normalizasyon yalnızca eğitimden hesaplandı. Küçük pilotun veri hattı hazır; standart fine-tuning girişinin UR5 veri sınıfına bağlanması ve ilk öğrenilmiş politikanın kapalı çevrim denemesi henüz yapılmadı. Büyük eğitimden önce rijit–yumuşak temas yapılabilirlik kontrolü de ayrı ele alınacak.

## Rijit sahnenin ilk küçük deneyi

Bu sahne artık çalışıyor. [Rijit yerleştirme raporu](RIGID-INSERTION-2026-11-15.md), üç fizik kontrolünü ve dört ofsetli uzman gösterimini kaydediyor. Aşağıdaki ölçütler ilk uygulamada kullanıldı; daha çeşitli senaryolar sonraki adımdır.

Başlangıçta aktif kavrama yerine UR5'e sabitlenmiş bir pim tool'u kullanılabilir; belge güvenli bir tool veya gripper düzenine izin veriyor. Pim ucunun bileğe göre dönüşümü ve tool'un kütle/ataleti kaydedilecek. Sahne geometrisi ilk simülasyon varsayımı olacak; gerçek laboratuvar aparatıyla eşleştiği ileri sürülmeyecek.

İlk sahnede önce üç ayrı kontrol yapılacak:

1. **Boşluk ve çarpışma:** Pim delikten geçerken duvarın içinden kaçmıyor mu? Delik kapalı bir katı olarak yanlış modellenmiş mi? Yanlış hizalı kontrol denemesi başarısız sayılıyor mu?
2. **TCP ve başarı:** Başarı, bileğin hedefe yakınlığıyla değil, ölçülen pim ucunun delik eksenine göre hizası ve yeterli giriş derinliğiyle hesaplanacak. Başarı birkaç ardışık adım sürmeli.
3. **Uzman ve kayıt:** İlk hizalı, kolay senaryoda betikli uzman çalışacak. Sonra küçük başlangıç ofsetleri ve açılar eklenecek; kamera, durum, eylem ve değerlendirme metadata'sı aynı bölümde tutulacak.

İlk başarı ölçütleri, seçilen pim çapı, delik çapı ve derinliğine göre yazılacak. Şu anki 1 mm hareket kontrolü eşiği, gelecekteki delik toleransı olarak kullanılmayacak. Temas sensörünün çıktısı birim/yön ve basit referans deneyiyle doğrulanmadan kuvvet başarısı raporlanmayacak.

## Eğitim ve test düzeni

- İlk insertion talimatı sabit: `Insert the peg into the hole.`
- Uzman simülatörün pim/delik gerçek pozlarını kullanabilir. Modelin girdisi RGB, proprio ve talimatla sınırlı kalır; gerçek hedef pozları değerlendirme bölümünde tutulur.
- Eğitim, doğrulama ve test senaryolarının kimlikleri ayrı manifestlerde saklanır. Normalizasyon istatistiklerine test verisi girmez.
- İlk fine-tuning küçük ve izlenebilir olacak. Sadece hedef eylemi tahmin edebilmek yeterli sayılmaz: modelin eylemi uygulanacak, yeni görüntü alınacak ve görev kapalı çevrimde değerlendirilecek.
- Ana ölçüler: insertion başarısı, tamamlama süresi, son hizalama hatası ve sıkışma/başarısızlık oranı. Tek denemelik başarı genel başarı oranı sayılmayacak.

## Yumuşak delik ve fiziksel robot

Belge, en geç 4. hafta civarında VLA içermeyen ayrı bir rijit pim–deforme olabilen delik testi istiyor. Deformasyonun gerçekten oluşması ve farklı adım/mesh ayarlarında kararlılık gösterilmesi gerekir. Kuvvete erişim güvenilir değilse rapora bu kısıt yazılır. Bu sonuç, rijit görev hattını durdurmaz.

Gerçek UR5 aşamasından önce robot varyantı, gripper/tool, kamera ve aparat ölçüleri laboratuvarla doğrulanacak. Bugünkü simülasyon kayıtları fiziksel robot doğrulaması olarak sunulmayacak.
