# Isaac Lab UR5 kamera ve hareket deneyi

İlk deney, sabit tabanlı UR5'in bilek bağlantısını taban çerçevesinin X yönünde 30 mm kaydırır. Diferansiyel ters kinematik, hedef poz ile ölçülen poz arasındaki hatadan eklem komutu üretir. Fizik 60 Hz, hedef ve kamera kaydı 20 Hz. Hedef 1,5 saniyede ilerler ve robotun hedefte oturması için 1 saniye tutulur.

Her kontrol adımında aynı simülasyon anından bir RGB kare ve ölçülen robot durumu kaydedilir. `target_increment_base_m`, arka arkaya iki referans konumun farkıdır. `target_position_base_m` kaydından mutlak referanslar yeniden oynatılır. Bu hareket pilotunda ölçüm noktası `wrist_3_link`. Ayrı [rijit görevde](../rigid-insertion/README.md) pim ucu için 72 mm TCP dönüşümü tanımlandı.

[İkinci hafta teslim kontrolü](../deliverables/week2/README.md), MP4 videosunu, ayrı VLA örneğini ve tekrar denetleme komutunu bir araya getirir.

## VALAR ortamı

VALAR giriş düğümünde Rocky Linux 8.9 ve glibc 2.28 gözlendi. Isaac Sim pip kurulumu glibc 2.35 veya üzerini bekliyor. Bu deney, kümedeki Singularity 4.3.2 modülüyle NVIDIA Isaac Lab 2.3.0 `linux/amd64` imajını kullanır. Doğrulanmış kısa hareket koşusu Tesla T4 üzerinde çalıştı; aşağıdaki komutlar bunu ister. SIF dosyası yaklaşık 8,34 GB (7,77 GiB). Açma işlemi ve çalışma dosyaları için `scratch` üzerinde ek alan gerekir. [Isaac Lab pip gereksinimleri](https://isaac-sim.github.io/IsaacLab/v2.3.1/source/setup/installation/pip_installation.html) · [NVIDIA imajı](https://catalog.ngc.nvidia.com/orgs/nvidia/-/containers/isaac-lab/2.3.0/tags) · [Isaac Sim sürücü gereksinimleri](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/requirements.html)

VALAR'da `vla-hpc/ur5-pilot` klasöründen imajı bir CPU işiyle hazırlayabilirsin.

```bash
sbatch --partition=ai --account=ai --qos=ai --mem=16G --time=1-00:00:00 job.slurm image
```

İmaj hazır olduğunda NVIDIA lisansını incele. Kabul ediyorsan ortam değişkenini ayarla. 15 Kasım'da yerçekimi açıkken ağırlık telafisi kullanan hareket kaydı ve delta eylem yeniden oynatması doğrulandı. Güncel ilk çalışma komutu aşağıdadır. [NVIDIA container ve lisans açıklaması](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/install_container.html)

```bash
export ACCEPT_EULA=Y
sbatch --partition=ai --account=ai --qos=ai --gres=gpu:tesla_t4:1 job.slurm record --gravity-compensation
```

## Çıktıları oku ve hareketi tekrar et

`IS_NO` yerine tamamlanan iş numarasını yaz.

```bash
cat runs/IS_NO/summary.json
sbatch --partition=ai --account=ai --qos=ai --gres=gpu:tesla_t4:1 \
    job.slurm replay runs/IS_NO/steps.jsonl --gravity-compensation --replay-actions
```

Her başarılı çalıştırma `runs/IS_NO/` içinde 50 eylem sonrası RGB PNG, bir başlangıç karesi `initial_rgb.png`, `motion.gif`, `steps.jsonl`, `summary.json`, `episode.json` ve `transitions.jsonl` üretir. [Ortak veri şeması](EPISODE_SCHEMA.md), 50 eylem ile 51 gözlemin nasıl bağlandığını açıklar.

Özet, kamera kalibrasyonunu, başlangıç/bitiş pozisyonunu ve takip ölçülerini içerir. Ağırlık telafili koşuda son konum ve en büyük Z hatası için 1 mm; ısınmadaki Z kayması için 1 mm; yönelim hatası için 1 derece sınırı kullanılır ve telafi torku kırpılmamalıdır. Eski telafisiz tanı koşullarında 12 mm kontrol eşiği korunur. Yeniden oynatma son konum farkı için ayrıca 5 mm eşik kullanılır. Bunlar hareket pilotunun ölçütleridir; pim–delik geometrisinin toleransı ayrıca tanımlanacak. [Isaac Lab diferansiyel IK örneği](https://isaac-sim.github.io/IsaacLab/v2.3.0/source/tutorials/05_controllers/run_diff_ik.html) · [NVIDIA UR5 varlığı](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/assets/usd_assets_robots.html#universalrobots)

## Z ekseninde aşağı kaymayı incele

15 Kasım'da eklenen ölçümler yerel ve VALAR CPU testlerinden geçti. T4 üzerinde yerçekimsiz X hareketi 50 kareyle kaydedildi ve iş başarıyla tamamlandı (`2025262_5`). Güncel telafili sonuçlar [kontrol raporunda](../CONTROL-AND-DATA-2026-11-15.md); telafisiz tanılar [ilk incelemede](../AUDIT-2026-11-15.md) saklanır. Bu deneyde henüz VLA, pim veya delik yok. Önce kamera, koordinat dönüşümleri ve robot kontrolünü doğruluyoruz.

Yerçekimi, robotun eklemlerine yük bindirir. Konum motoru hedef açı ile ölçülen açı arasındaki farkı azaltmaya çalışır. Sonuç; motor sertliği, sönümleme, kuvvet sınırı ve kontrol döngüsüne bağlıdır. Bu nedenle yerçekimini kapatınca düzelme görmek, tek başına bir kök neden veya fiziksel olarak doğru bir çözüm kanıtlamaz. Isaac Lab'de `disable_gravity` robotun rijit gövdelerine uygulanır; zemin ve diğer nesnelerin yerçekimini değiştirmiyoruz. [Isaac Lab 2.3 fizik ayarı](https://github.com/isaac-sim/IsaacLab/blob/v2.3.0/source/isaaclab/isaaclab/sim/schemas/schemas_cfg.py)

Aynı başlangıç açıları, 60 Hz fizik, 20 Hz kontrol, 12 fizik adımlık ısınma ve 800/60 motor kazançlarıyla altı kısa koşu:

| Dizi numarası | Kontrol | Robot yerçekimi | Amaç |
| --- | --- | --- | --- |
| 0 | Eklem açı hedefleri sabit | Açık | IK olmadan başlangıç açıları korunuyor mu? |
| 1 | Eklem açı hedefleri sabit | Kapalı | Yerçekimi yükü kaldırılınca fark ne? |
| 2 | Bilek konumu ve yönelimi IK ile sabit | Açık | Sabit Kartezyen hedefte takip nasıl? |
| 3 | Bilek konumu ve yönelimi IK ile sabit | Kapalı | Aynı hedefte yerçekimi etkisi ne? |
| 4 | Bilek X yönünde 30 mm ilerliyor | Açık | Hareket sırasında Z ve yönelim korunuyor mu? |
| 5 | Bilek X yönünde 30 mm ilerliyor | Kapalı | Hareket ile yerçekimi etkileşimi ne? |

```bash
export ACCEPT_EULA=Y
sbatch --partition=ai --account=ai --qos=ai --gres=gpu:rtx_a6000:1 \
    --job-name=ur5-diag --array=0-5%1 job.slurm diagnose
```

`%1` en fazla bir koşunun aynı anda GPU kullanmasını sağlar. Çıktılar `runs/DIZI_IS_NO_0/` ... `runs/DIZI_IS_NO_5/` klasörlerine yazılır. Bir koşu takip eşiğini aşsa bile diğer dizi işleri ölçüm yapabilir. Slurm'da `FAILED` görülürse `summary.json` olup olmadığına ve günlüğe bak: takip hatası ile programın açılmaması farklı durumlardır.

Kısa 320×240 sahne 15 Kasım'da `--gres=gpu:tesla_t4:1` ile de çalıştırıldı. OpenVLA'nın BF16 değerlendirmesi için A40 seçimi ayrı tutulur. Kit shader önbelleği `.runtime/kit-cache/` içinde yeniden kullanılır ve aynı önbelleği kullanan çalıştırmalar `flock` ile sıraya girer. Her işin veri/günlük klasörü ayrıdır. Her iş çalıştıracağı kaynak dosyaları `.runtime/code-IS_NO/` içine kopyalar; çalışma sırasında ana kod değişse de o iş kendi kopyasını kullanır.

Isaac Sim 5.1'in tam kapanışı bu sahnede kayıt tamamlandıktan sonra takıldı. PNG, JSON ve GIF yazmaları kapandıktan sonra `SimulationApp.close(wait_for_replicator=False, skip_cleanup=True)` kullanılır. Bu, NVIDIA'nın [belgelenmiş hemen kapanış seçeneğidir](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/py/source/extensions/isaacsim.simulation_app/docs/index.html). Simülatör süreç durumunu 0 yapabildiği için `check_pilot.py` sonucun gerçekten başarılı olduğunu ayrıca denetler. Kapanış gözcüsü 45 saniye, container çalıştırma sınırı 12 dakikadır.

Bir koşuyu veya mevcut eski kaydı analiz etmek için Isaac Lab gerekmez:

```bash
python3 diagnostics.py runs/IS_NO
python3 diagnostics.py runs/DIZI_IS_NO_0 runs/DIZI_IS_NO_1 --output comparison.json
```

`max_abs_tracking_error_xyz_m[2]`, örneklenen kontrol adımları arasındaki en büyük mutlak Z hedef hatasıdır. `z_displacement_range_m`, başlangıca göre gözlenen en düşük ve en yüksek Z değişimidir. İkisi farklıdır: hedef zaten aşağı gidiyorsa aşağı hareket takip hatası olmayabilir. Değerler metre; milimetreye çevirmek için 1000 ile çarp. Ölçümler 20 Hz'deki örnekleri kapsar, aradaki tüm fizik anlarını kapsamaz.

Yeni `config.json` yerçekimini, başlangıcı, motor kazançlarını, simülasyondaki eklem sınırlarını ve kullanılan USD yolunu saklar. `steps.jsonl` artık komut verilen eklem açılarını, ölçülen hızları, dünya ve taban pozlarını, IK adım kısıtlamasını ve eklem sınırına takılmayı da içerir. Özet ısınma sırasındaki kaymayı ve tüm kayıt boyunca XYZ hatalarını verir. Telafisiz tarihsel tanı koşullarında son konum ve örneklenen Z hatası için 12 mm eşik kullanıldı. Güncel telafili koşuda bu iki eşik 1 mm; yönelim 1° ve ısınma kayması 1 mm ile sınırlıdır. Rijit insertion başarısı kendi geometri ölçütleriyle hesaplanır.

İlk yorum sırası:

1. Tabanın dünya konumu değişiyorsa sabit taban ve varlık ayarlarını incele.
2. Eklem sabit tutmada sadece yerçekimi açıkken sarkma artıyorsa motor takibi, kuvvet sınırları ve yerçekimi yükünü araştır.
3. Eklem sabit tutma düzgün, IK ile sabit tutma bozuksa Jacobian, koordinat çerçevesi ve IK komutlarını araştır.
4. İkisi düzgün, X hareketi bozuksa hareket hızı, IK adım sınırı, tekilliğe yakınlık ve eklem sınırlarına bak.
5. Isınma sırasında büyük kayma varsa aynı karşılaştırmayı daha uzun ısınmayla tekrarla; diğer ayarları aynı tut.

Tek koşu örneği: `job.slurm record --motion hold --disable-gravity --warmup-steps 120`. Yerçekimi kapalı kaydı yeniden oynatırken `job.slurm replay runs/IS_NO/steps.jsonl --disable-gravity` kullan. Yeni kayıtların kritik ayarları farklıysa yeniden oynatma durur. Eski kayıtlarda ayar dosyası yoksa bu karşılaştırma güvence altına alınamaz. Yönelim artık kayıt dosyasındaki hedeflerden aynen okunur.

CPU kontrolleri:

```bash
python3 -m unittest discover -s . -p 'test_*.py' -v
```
