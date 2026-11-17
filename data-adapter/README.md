# UR5 kayıtlarını OpenVLA verisine dönüştürme

Bu aşama, robotun kaydedilmiş uzman hareketlerini modelin okuyabileceği biçime çevirir. Model henüz UR5 üzerinde eğitilmez veya çalıştırılmaz. Simülatörün gerçek delik pozunu bilen betikli uzman, veri üretmek için kullanılır; bu bilgi modelin girdisine girmez.

15 Kasım'daki `2028146` işi tamamlandı ve tüm uçtan uca kontroller geçti: [doğrulama JSON'u](../audit/2026-11-15/adapter-reference/adapter_verification.json). [Sonuç raporu](../ANGULAR-DATASET-2026-11-15.md), ölçümleri ve bu küçük pilotta test değerlerinin normalizasyon sınırına takılma kısıtını açıklar.

## Küçük veri seti nasıl ayrılıyor?

`../rigid-insertion/pilot_manifest.json`, başlangıç konumu ve açısını önceden sabitler. 8 senaryo eğitim, 2 senaryo doğrulama, 2 senaryo test içindir. Aynı fiziksel parametreler iki farklı bölüme konulamaz. Her bölüm manifestin SHA-256 özetini ve senaryo kimliğini taşır. Dönüştürücü, 12 senaryonun her birinden tam olarak bir başarılı kayıt ister; eksik, tekrarlanan veya farklı manifestten kayıtları reddeder.

- **Eğitim:** Modelin ağırlıklarını ve normalizasyon istatistiklerini öğrenmek için kullanılır.
- **Doğrulama:** Eğitim sırasında hataları ve ayarları izlemek için kullanılır; istatistiklere katılmaz.
- **Test:** Son kapalı çevrim değerlendirmesine ayrılır. Eğitim yükleyicisi bu bölümü açmayı reddeder.

Bu 12 bölüm, dönüşüm hattının ilk kontrolüdür. Ortak kamera/ışık/geometri ve sabit talimatla çekilir. Daha fazla veri, farklı tohumlar ve yeni bir saklı test seti olmadan geniş genelleme iddiası kurulamaz. Manifest, sonuçlar görüldükten sonra yeniden bölünmez.

## Modele hangi bilgiler gidiyor?

| Alan | Anlamı |
| --- | --- |
| RGB | Eylemden hemen önceki sabit dış kamera görüntüsü |
| Talimat | `Insert the peg into the hole.` |
| 8 boyutlu proprio | Ölçülen TCP XYZ, yönelim rotasyon vektörü ve sabit tool için iki sıfır |
| 7 boyutlu eylem etiketi | Taban çerçevesinde XYZ farkı, sol çarpımlı yönelim farkı ve sabit tool için sıfır |

Delik gerçek pozu, uzman hedef pozu, başarı ölçüleri ve ham temas sinyali eğitim gözlemine eklenmez. Bunlar yerel değerlendirme kayıtlarında tutulur. Sabit tool için gripper sinyali üretilmez.

Her doğal bölüm 150 geçiş ve 151 görüntü içerir. RLDS, bölümleri standart bir veri düzeninde saklama yaklaşımıdır; TFDS bu veriyi diskte okuyup yazan kütüphanedir. `ur5_tfds.py`, 150 eylem satırına son gözlemi ayrı terminal satırı olarak ekler. Terminal satırındaki sıfır eylem yalnızca yer tutucudur. `ur5_loader.py` bu satırı eylem normalizasyonundan ve chunk oluşturmadan önce çıkarır.

## Normalizasyon ve eylem chunk'ı

Metre ve radyan cinsinden küçük sayılar model için yaklaşık −1…1 aralığına çevrilir. `adapter_core.py`, yalnızca 8 eğitim bölümündeki 1.200 eylem/gözlem çiftinden istatistik hesaplar. Test görüntüsü veya doğrulama eylemi bu hesaba girmez. Kaynak kayıt özetleri `train_statistics.json` içinde saklanır.

Kullanılan yöntem OpenVLA'nın `BOUNDS_Q99` yöntemidir: %1 ve %99 sınırları dışında kalan değerler kırpılır. Neredeyse sabit eksenlerde simülasyon gürültüsünü büyütmemek için en küçük aralıklar uygulanır: eylemde 0,1 mm / 0,001 rad; proprio'da 1 mm / 0,01 rad. Ham yüzdelikler ve uygulanan sınırlar ayrı tutulur. Sabit tool boyutları sıfır kalır. Bölüm başına ve eksen başına sınır dışı örnek sayıları raporlanır; doğrulama/test sonucuna bakılarak sınırlar yeniden hesaplanmaz.

Model tek görüntüden art arda 8 eylem tahmin edecek biçimde hazırlanır. Buna eylem chunk'ı denir. Kullanılan sabit OpenVLA sürümü, her bölümün son 7 başlangıç indeksini atar. Böylece 150 eylemden 143 tam chunk çıkar; bir chunk başka bölüme taşmaz ve terminal yer tutucusu etiket olmaz. Eğitimde 1.144, doğrulamada 286 chunk beklenir.

## Gerçek yükleyiciyle uyumluluk

Kaynak sürüm `e4287e94541f459edc4feabc4e181f537cd569a8` olarak sabittir. Üreticinin dosyaları değiştirilmez. `UR5RLDSDataset`, aynı PyTorch örnek arayüzünü sağlar; üreticinin normalizasyonunu, chunk dönüşümünü, görüntü dönüşümünü, `RLDSBatchTransform` sınıfını ve collator'ını kullanır. UR5 profili açıkça 7 eylem, 8 proprio, 8 eylemlik chunk ve tek dış kamera olarak tanımlanır. Boyutların LIBERO ile aynı olması, UR5 eylemlerinin anlamının veya model başarısının aynı olduğu anlamına gelmez.

İki önemli üretici ayrıntısı bu adaptörde açıkça ele alınır:

1. [Normal yükleyici](https://github.com/moojink/openvla-oft/blob/e4287e94541f459edc4feabc4e181f537cd569a8/prismatic/vla/datasets/rlds/dataset.py), istatistik verilmezse bütün bölümleri tarar. Biz eğitimden hesaplanmış istatistikleri zorunlu olarak geçiririz.
2. [Chunk dönüşümü](https://github.com/moojink/openvla-oft/blob/e4287e94541f459edc4feabc4e181f537cd569a8/prismatic/vla/datasets/rlds/traj_transforms.py), bölümün son 7 başlangıcını düşürür. Kontrolümüz bu gerçek davranışa göre yapılır.

Standart `finetune.py` henüz bu sınıfı seçmez. Sonraki eğitim girişinde veri sınıfının açıkça bağlanması, checkpoint/başlık seçimi ve UR5 kapalı çevrim eylem uygulaması gerekir. Bu aşamanın geçmesi, eğitimin tamamlandığı anlamına gelmez.

PyTorch eğitim arayüzü, eğitim chunk'larını 17 tohumu ve 256 örneklik tamponla karıştırıp tekrar eder. Doğrulama akışı sonludur ve karıştırılmaz. Her chunk, karıştırmadan önce tek bölümün içinde oluşturulur.

## VALAR'da yeniden çalıştırma

Önce 12 senaryonun GPU işi tamamlanır:

```bash
cd /scratch/HPC_USER/vla-hpc/rigid-insertion
sbatch --partition=ai --account=ai --qos=ai --gres=gpu:tesla_t4:1 \
  --export=ALL,ACCEPT_EULA=Y --array=0-11%1 job.slurm dataset
```

Çıkan dizi iş numarasını aşağıda `DIZI_NO` yerine yaz. CPU veri işi, GPU dizisinin bütün görevleri başarılı bittikten sonra başlar:

```bash
cd /scratch/HPC_USER/vla-hpc/data-adapter
sbatch --partition=ai --account=ai --qos=ai \
  --dependency=afterok:DIZI_NO job.slurm DIZI_NO
```

Her çalıştırma ayrı `builds/IS_NO/` klasörü oluşturur. `adapter_verification.json` ancak tüm kontroller geçerse yazılır. Bu kontrol 1.812 TFDS görüntüsünü kaynak PNG'lerle piksel piksel, 1.800 gerçek eylemi kaynak kayıtla, tüm eğitim/doğrulama chunk'larını beklenen dizilerle karşılaştırır. Ardından önbellekteki gerçek processor/tokenizer ile iki örneklik bir eğitim batch'i hazırlar; 7B ağırlıkları yüklemez.

Durum için VALAR'daki `vla-hpc` klasöründe `bash status.sh` çalıştırılır. `build_summary.json`, dosyanın oluşturulduğunu; `adapter_verification.json`, uçtan uca veri kontrolünün de geçtiğini gösterir.
