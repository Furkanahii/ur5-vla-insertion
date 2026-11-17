# Başlatılan işlerin kapanış envanteri

15 Kasım 2026'da ikinci hafta kapsamı için kontrol edildi. Tamamlanmış küçük pilot ile henüz başlanmamış araştırma aşaması ayrı kaydedilir. Tarihsel başarısız tanılar korunur; kabul edilmiş nihai çıktıların yerine kullanılmaz.

| Başlatılan iş | Kapanış kanıtı | Kalan kapsam/sınır |
| --- | --- | --- |
| Koç erişimi ve Python ortamı | SSH çalışıyor; `verify_environment.py`, pip check ve kaynak sürümleri geçiyor | VPN/MFA oturumları süreli; yeniden bağlanma kurulum eksikliği değildir |
| Isaac Lab imaj indirme/kurma | amd64 SIF tablosu okunuyor; çalışan UR5 işleri var | İmaj ve lisans kullanıcı çalışma alanında kalır |
| Hazır VLA örneği | `1952021`: LIBERO-10, 10 bölüm / 10 MP4; tam video çözme kontrolü | Tek deneme/görev; UR5 insertion sonucu değildir |
| UR5 yerçekimi ve Z kayması tanısı | Altı karşılaştırma; telafili kayıt `2025430` ve delta replay `2025475` geçti | Eski telafisiz `FAILED` işler bilinen tanı sonuçlarıdır |
| Ortak bölüm arayüzü | 14 şema/kontrol testi; gerçek kayıt ve replay | İki öğrencinin ortak incelemesi `TEAM-01` |
| Rijit pim–delik ve negatif kontroller | Yeni kaynakla `2028002_0…2`: açık delik başarılı, kenar/kapak engelleniyor | Ham normal kuvvet tam ve doğrulanmış wrench sayılmaz |
| Açılı başlangıç ve veri ayrımı | `2027958_0…11`: 12/12 uzman başarısı; sabit manifest/kamera | Dönüşüm pilotu, geniş benchmark değildir |
| RLDS/TFDS ve gerçek OpenVLA batch'i | `2028146`: 1.812 görüntü / 1.800 eylem; 1.144 eğitim / 286 doğrulama chunk'ı | Fine-tuning girişine bağlantı henüz başlatılmadı; pilot normalizasyon sınırı raporlandı |
| Kaynak sürümleme ve teslim | Bağımsız yerel Git ve özel VALAR bare repo; ikinci hafta etiketi | GitHub için temiz kaynak ve küçük kanıt kopyası hazırlandı; tam veri yetkili çalışma alanında korunur |

Şu an başlatılmış ve kuyrukta unutulmuş bir indirme, kurulum veya GPU deneyi yoktur. En son ortam kontrolü kuyruk listesini `deliverables/week2/environment.json` içine kaydeder.

## Henüz başlatılmayanlar

- İki öğrencinin ortak şema incelemesi ve sonraki çalışma seçimi.
- Yumuşak delik temas yapılabilirliği: belgedeki 3–4. hafta hedefi.
- Daha büyük gösterim seti ve yeni sabit manifest.
- UR5 fine-tuning girişinin hazırlanması, ağırlık eğitimi ve öğrenilmiş kapalı çevrim rollout.
- Basit görsel/BC baseline ve nicel model karşılaştırması.
- Fiziksel UR5, kamera/tool kalibrasyonu ve gerçek kuvvet ölçümü.

Bu maddeler eksik kalmış ikinci hafta kurulumları olarak işaretlenmez; sonraki takvim hedefleridir. Şimdiki odak [ikinci hafta teslimi](deliverables/week2/README.md) ve ekipçe anlaşılmasıdır.
