# Durum — 17 Kasım 2026

Bu sayfa tamamlanan kanıtları ve sonraki işleri ayırır. Son GPU referansları 15 Kasım; küçük paylaşım paketi kontrolü 16 Kasım tarihlidir. GitHub teslimi yeni GPU deneyi içermez.

| Kapsam | Sonuç |
| --- | --- |
| 1–2. hafta teknik ödevi | Tamamlandı; ortak öğrenci incelemesi açık |
| 3–4. hafta rijit görev | Sabit pim, açık delik, betikli uzman ve fizik kontrolleri hazır |
| Veri sözleşmesi / adaptör | Replay ve gerçek OpenVLA processor/collator batch kontrolü geçti |
| Küçük gösterim seti | 12/12 uzman başarısı; 8 train / 2 validation / 2 test |
| Yumuşak delik | Başlanmadı; 4. hafta yapılabilirlik hedefi |
| UR5 VLA eğitimi ve öğrenilmiş rollout | Başlanmadı; 5–6. hafta hedefi |
| Fiziksel UR5 | Sonraki laboratuvar aşaması |

## Sonuçları nasıl yorumlayalım?

- LIBERO'daki 10/10, görev başına tek ilk denemedir; kapsamlı başarı oranı değildir.
- UR5'teki 12/12, gerçek pozu bilen betikli uzman sonucudur; VLA başarısı değildir.
- Rijit fizik kontrolleri: açık delikte yaklaşık 20 mm giriş; kenar ve kapak senaryolarında giriş engellenmesi.
- Z sarkması tanısında eski yaklaşık 30,7 mm hata, yerçekimi telafili hareket kaydında en fazla yaklaşık 0,18 mm'ye indi.
- Küçük veri setinde test proprio değerlerinin normalizasyon sınırına takılması raporlandı; bu set geniş genelleme sonucu için yeterli değildir.
- Ham temas normal kuvvetleri, doğrulanmış tam wrench/kuvvet kalibrasyonu değildir.
- 16 Kasım son uzak bağlantı kontrolünde SSH zaman aşımı vardı. Bu, yeni GPU koşusu yapıldığı veya güncel küme sağlığının doğrulandığı anlamına gelmez.

## Sonraki işler

1. İki öğrencinin şema ve örnek bölüm incelemesi.
2. Rijit pim–deforme olabilen delik için küçük temas/kararlılık deneyi.
3. Daha geniş veri kapsamı ve bağımsız test manifesti.
4. Adaptörün fine-tuning girişine bağlanması, küçük eğitim ve UR5 kapalı çevrim denemesi.

[Ayrıntılı araştırma planı](../PROJECT_ROADMAP.md) · [Başlatılan işler](../STARTED_WORK.md) · [Ekip kaydı](../ISSUES.md)
