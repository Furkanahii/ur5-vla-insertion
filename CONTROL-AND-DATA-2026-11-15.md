# Yerçekimi açık UR5 kontrolü ve ortak veri formatı

Bu temel arayüzden sonra [rijit pim–delik sahnesi ve ilk uzman gösterimleri](RIGID-INSERTION-2026-11-15.md) de çalıştırıldı. Aşağıdaki sonuçlar, o görevin dayandığı hareket ve veri kontrolleridir.

Proje belgesindeki ilk ödevin hareket ve ortak veri arayüzü kısmı ilerletildi: UR5 artık yerçekimi açıkken ağırlık telafisiyle 30 mm X hareketini takip ediyor. Yeni gözlem–eylem formatı gerçek GPU kaydı ve delta eylemlerle yeniden oynatma üzerinde doğrulandı. Bu aşamada pim–delik görevi veya UR5 üzerinde VLA eğitimi yapılmadı.

## Kontrol sonucu

| Ölçüm | Yerçekimi açık, telafisiz `2025274_4` | Yerçekimi açık, telafili `2025430` |
| --- | --- | --- |
| Isınmada Z değişimi | -27,488 mm | Ölçülen değişim 0 mm |
| Hareket boyunca en büyük mutlak Z hedef hatası | 30,699 mm | 0,179 mm |
| Son konum hatası | 30,618 mm | 0,00267 mm |
| En büyük yönelim hatası | 3,3882 derece | 0,0182 derece |
| Takip kabulü | Geçmedi | Geçti |

İlk tork telafisi işi `2025405` de geçti. Yeni formatlı kayıt `2025430` 72 saniyede, delta eylem yeniden oynatması `2025475` 71 saniyede `COMPLETED` oldu. Yeniden oynatmada son konum farkı 0,56 mikrometre; bütün 50 örnekteki en büyük konum farkı 0,69 mikrometre olarak ölçüldü.

[Ölçüm verileri](audit/2026-11-15/phase-2/results.json) · [Karşılaştırma grafiği](audit/2026-11-15/phase-2/gravity-compensation.png) · [Yerçekimi açık hareket GIF'i](audit/2026-11-15/motion-reference/motion.gif)

## Ne değişti

Robotun yerçekimi etkin kaldı. Her fizik adımında PhysX'in `get_gravity_compensation_forces()` çıktısı eklem torku olarak motor komutuna eklendi; ısınma sırasında da uygulandı. Tork tensorunun boyutu ve sonlu değerleri kontrol edildi, nominal eklem kuvvet sınırlarına göre kırpma ve kırpılma sayısı kaydedildi. Bu koşuda tepe telafi komutu 29,39 Nm ve kırpılan adım sayısı 0.

Motor kazançları 800/60, fizik 60 Hz, kontrol 20 Hz olarak korundu. Telafili koşuda son konum ve en büyük Z hatası için 1 mm, ısınma kayması için 1 mm, yönelim için 1 derece sınırı kullanıldı. Bu ölçütler ilk hareket deneyi içindir; insertion toleransı pim–delik geometrisinden türetilecek.

Kullanılan API'nin çıktısı sabit tabanlı robot için altı eklem boyutundadır. [Omni Physics API](https://docs.omniverse.nvidia.com/kit/docs/omni_physics/107.0/extensions/runtime/source/omni.physics.tensors/docs/api/python.html) ve [Isaac Lab 2.3 implicit motorunun feed-forward arayüzü](https://github.com/isaac-sim/IsaacLab/blob/v2.3.0/source/isaaclab/isaaclab/actuators/actuator_pd.py) kontrol edildi. Kayıtlı torklar ağırlık telafisi komutlarıdır; doğrulanmış temas kuvveti ölçümü olarak kullanılmıyor.

## Ortak kayıt formatı

`episode.json` ve `transitions.jsonl`, yeni bir bölümün arayüzünü ve sıralı geçişlerini saklar:

`görüntü ve ölçülen durum[t] → delta eylem[t] → yeni görüntü ve durum[t+1]`

50 eylem için 51 gözlem vardır. İlk görüntü ayrıca kaydedilir. Eylem, bir önceki hedefe göre değil, komut öncesinde ölçülen robot durumuna göre hesaplanır. Metre/radyan, wxyz quaternion, taban çerçevesinde rotasyon vektörü ve soldan yönelim bileşimi açıkça tanımlandı.

Delta eylem yeniden oynatması, kayıtlı mutlak hedefi kopyalamak yerine her adımda yeni ölçülen durumdan hedefi tekrar oluşturdu. Böylece eylem arayüzü gerçek simülasyon döngüsünde test edildi.

Model girdi fonksiyonu yalnızca RGB, proprio ve dil talimatını seçiyor. Hedef poz değerlendirme bölümünde kalıyor. Temas sensörü henüz olmadığı için wrench alanı `null`, doğrulanmış kuvvet bayrağı `false`. Hareket pilotu, insertion eğitimine uygun değil olarak işaretlendi.

[Öğretici şema rehberi](ur5-pilot/EPISODE_SCHEMA.md) · [Örnek bölüm metadata'sı](audit/2026-11-15/motion-reference/episode.json)

## Nasıl doğrulandı

- Yerel Mac ve VALAR ortamında 14 CPU regresyon testi geçti. Testler görüntü–eylem zaman sırasını, zincir sürekliliğini, rotasyon bileşimini, model girdisinden değerlendirme bilgisinin ayrılmasını ve hatalı kayıtların reddini kapsıyor.
- Mac ve Linux arasındaki yaklaşık 1e-16 sayısal fark gözlendi. Sayısal zincir için 1e-9 tolerans kullanılıyor; görüntü kimliği ve adım sırası kesin denetleniyor. 1e-4 rad eklem tutarsızlığı reddediliyor.
- Yeni üç koşunun toplam 152 PNG dosyası PIL ile açılıp doğrulandı.
- Kayıt ve yeniden oynatma hem sunucuda hem Mac'te bağımsız sonuç kontrolünden geçti.
- Her GPU işi kaynak dosyalarını ayrı kopyada çalıştırdı ve SHA-256 kaydetti. Sonradan üretilen bölüm yan dosyası ayrıca `exporter_sha256` içeriyor; ham simülasyon kaydı korunuyor.

## Bu rapordan sonraki tamamlanan işler

[Proje yol haritası](PROJECT_ROADMAP.md), ilk belgedeki teslimlerle mevcut durumu eşleştiriyor. Bu raporun ardından rijit pim, fiziksel delik, pim ucu TCP, ölçülen giriş başarısı ve ayrı konum/açı senaryoları tamamlandı. Güncel kanıtlar [açılı veri seti raporundadır](ANGULAR-DATASET-2026-11-15.md).

Bu kontrol sonucu tek UR5 başlangıç duruşu ve 30 mm X hareketi için doğrulandı. Pim kütlesi, farklı duruşlar ve temas eklendiğinde tekrar sınanacak. Ortak şema ham geçişleri saklar; sonradan hazırlanan [RLDS adaptörü](data-adapter/README.md) yalnızca manifestli insertion bölümlerinden eğitim istatistiklerini hesapladı ve gerçek OpenVLA batch kontrolünden geçti. UR5 fine-tuning başlatılmadı. Belgede istenen ayrı yumuşak delik yapılabilirlik kontrolü de yol haritasında duruyor.
