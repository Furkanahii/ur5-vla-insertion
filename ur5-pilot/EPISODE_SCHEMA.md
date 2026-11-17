# UR5 ortak gözlem ve eylem formatı

Bu format, simülasyon ile model tarafının aynı birimleri, koordinatları ve zaman sırasını kullanmasını sağlar. İlk doğrulama verisi robotun bileğini hareket ettirir. Pim veya delik içermeyen bu kayıtlar insertion eğitiminden açıkça dışlanır.

## Bir kontrol adımı

`observation[t] → action[t] → next_observation[t]`

20 Hz kontrol, adımlar arasında 0,05 saniye demektir. İlk gözlem `initial_rgb.png` dosyasındadır. İlk eylemden sonraki görüntü `rgb/0000.png`; ikinci eylemin başlangıç görüntüsü de aynı dosyadır. 50 eylem için 51 gözlem vardır.

`steps.jsonl`, ayrıntılı simülatör günlüğüdür. `episode.json` arayüz ve kalibrasyon bilgilerini; `transitions.jsonl` yukarıdaki üçlüleri saklar. Eski, yalnızca eylem sonrası kare içeren kayıtlara eksik başlangıç görüntüsü uydurulmaz.

## Gözlem

| Alan | Anlam |
| --- | --- |
| `rgb` | Kayıt klasörüne göre göreli RGB PNG yolu |
| `time_s` | Simülasyon zamanı; bilgisayarın duvar saati değil |
| `tcp_position_base_m` | Kontrol edilen noktanın robot tabanına göre XYZ konumu; metre |
| `tcp_orientation_base_wxyz` | Aynı noktanın yönelimi; quaternion sırası w,x,y,z |
| `joint_positions_rad`, `joint_velocities_rad_s` | Altı eklemin ölçülen açıları ve hızları |
| `proprio` | TCP konumu 3 + yönelim rotasyon vektörü 3 + sabit gripper kanalları 2 = 8 sayı |

**TCP**, uçta kontrol ettiğimiz referans noktasıdır. Bu pilotta TCP, `wrist_3_link` ile aynı noktadır; ofset sıfırdır. Ayrı rijit görevde pim ucunun yeni dönüşümü tanımlanmıştır; hareket pilotunun sıfır ofseti korunur. Sabit gripper kanalları gerçek parmak ölçümü değildir; bu pilotta hareketli gripper bulunmadığını belirten sıfır kanallarıdır. Eklem sırası `episode.json` içindeki `joint_names` alanında saklanır.

[Rijit yerleştirme görevinde](../rigid-insertion/README.md) TCP artık pim ucudur: tool gövdesinden 72 mm uzakta ve +Z ekseni bileğe doğru tanımlıdır. Bu görevin metadata'sı çeviri ve yönelim ofsetini `tcp_offset_m_wxyz` içinde saklar. Böylece aşağı dönük pimin rotasyon vektöründe +180°/−180° yapay sıçraması önlenir. Veri okuyucusu her bölümün tool/TCP metadata'sını kullanmalıdır.

## Eylem

Yedi sayının sırası:

`[dx, dy, dz, drot_x, drot_y, drot_z, fixed_tool_command]`

İlk üç sayı metre, sonraki üç sayı radyandır. Son kanal sabit tool için sıfırdır. Pozisyon farkı, komut verilmeden hemen önce ölçülen TCP konumundan hesaplanır; bir önceki hedef konumdan değil.

Yönelim farkı taban çerçevesindedir ve soldan uygulanır:

`q_target = q_delta × q_observed`

Buradaki `drot` üçlüsü Euler açıları değildir; yönü dönme eksenini, uzunluğu dönme miktarını veren rotasyon vektörüdür. `pose_delta` ile `apply_delta` birbirinin tersi olarak sınanır. CPU testi, iki farklı eksendeki 90 derece dönmelerle çarpma sırasını da kontrol eder.

Pilot kalite raporu, adım başına 5 mm / 0,05 rad sınırlarını ayrıca belirtir. Bu ilk kontrol sınırları pim–delik geometrisinden türetilmiş insertion toleransları değildir. Eylemler dosyada fiziksel birimleriyle tutulur; henüz normalize edilmez.

## Model girdisi ile değerlendirme verisi

`model_inputs` yalnızca görüntü yolu, proprio vektörü ve dil talimatını döndürür. Hedef konumu, gelecekte eklenecek pim–delik gerçek konumlarını veya başarı etiketini model girdisine katmaz. Hedef poz yalnızca `evaluation` altında tutulur.

Temas ölçümü henüz doğrulanmadığı için `contact.status = not_instrumented`, `wrench_validated = false`, `wrench = null`. Ağırlık telafisi için kaydedilen eklem torkları, bu alanı dolduran bir temas ölçümü olarak kullanılmaz.

## OpenVLA bağlantısı

Kullandığımız sabit OpenVLA-OFT sürümünün LIBERO ayarı 7 eylem, 8 proprio kanalı ve 8 eylemlik chunk kullanır. [Resmî sabitler](https://github.com/moojink/openvla-oft/blob/e4287e94541f459edc4feabc4e181f537cd569a8/prismatic/vla/constants.py)

Bu boyutların aynı olması, LIBERO ağırlıklarının UR5 görevi için hazır olduğu anlamına gelmez. UR5 için [veri adaptörü](../data-adapter/README.md), tek dış kamera ve eylem ölçekleme kontrolleri tamamlandı; fine-tuning henüz başlamadı. Bu ortak şema ham, tek adımlık geçişler tutar. Adaptör, ayrı manifestli insertion bölümlerini doğrulanmış bir RLDS/TFDS veri setine çevirir; hareket pilotu insertion eğitiminden dışlanır.

Tamamlanan ilk insertion veri setinde:

1. Gösterimler senaryo kimlikleriyle eğitim/doğrulama/test olarak ayrıldı.
2. Normalizasyon istatistikleri yalnızca eğitim bölümünden hesaplandı. Sabit tool kanalı normalize edilmedi.
3. Sekizli eylem grupları bir bölümün sonundan başka bir bölüme taşmıyor. Kurulu OpenVLA sürümü son 7 başlangıç indeksini atıyor; terminal yer tutucusu eğitim etiketlerine girmiyor. Bütün chunk'lar özgün eylemlerle karşılaştırıldı.
4. Isaac kamera görüntülerine LIBERO'ya özgü 180 derece çevirme işlemi otomatik uygulanmadı.
5. İlk görev talimatı belgede olduğu gibi sabit tutuldu: `Insert the peg into the hole.` Bu hareket pilotunun talimatı ise yaptığı hareketi tarif eder.

## Kontroller

```bash
python3 -m unittest discover -s . -p 'test_*.py' -v
python3 episode.py runs/IS_NO
```

Eylem arayüzünden yeniden oynatma:

```bash
sbatch --partition=ai --account=ai --qos=ai --gres=gpu:tesla_t4:1 \
  --export=ALL,ACCEPT_EULA=Y job.slurm replay runs/IS_NO/steps.jsonl \
  --gravity-compensation --replay-actions
```

Bu komut kayıtlı delta eylemlerini yeni ölçülen durumla birleştirir. Mutlak hedefleri doğrudan kopyalayan eski yeniden oynatmadan farklı bir arayüz kontrolüdür.
