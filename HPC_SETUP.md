# Koç HPC üzerinde UR5 ve OpenVLA çalışma alanı

**Mevcut takvim: 2. hafta.** [İkinci hafta teslimi ve kontrolü](deliverables/week2/README.md), bu haftanın gerekliliklerini çalışan kanıtlarla toplar. [Başlatılan işler envanteri](STARTED_WORK.md) tamamlanan pilotları ve henüz başlanmayan aşamaları ayırır. Bu denetimde yeni eğitim veya deney başlatılmadı.

Bu çalışma alanı, Isaac Lab üzerinde UR5 yerleştirme projesinin altyapısını tutar. Hazır OpenVLA-OFT ağırlıklarıyla LIBERO-10 üzerinde görev başına bir deneme tamamlandı. [UR5 kamera ve hareket deneyi](ur5-pilot/README.md) ayrı bir Singularity ortamında çalışır.

[Proje yol haritası](PROJECT_ROADMAP.md) · [Yerçekimi açık kontrol ve ortak veri formatı sonucu](CONTROL-AND-DATA-2026-11-15.md) · [Veri şeması](ur5-pilot/EPISODE_SCHEMA.md)

[Rijit pim–delik görevi ve ilk uzman gösterimleri](RIGID-INSERTION-2026-11-15.md) çalışıyor. [Görev rehberi](rigid-insertion/README.md), açık delik, kenar ve kapak kontrolleri ile dört küçük başlangıç ofsetini yeniden üretir.

[Açılı başlangıçlar ve ilk ayrık veri seti](ANGULAR-DATASET-2026-11-15.md) de tamamlandı: 12 uzman bölümü, 1.800 eylem, 1.812 görüntü ve gerçek OpenVLA veri yükleme kontrolü. [Veri adaptörü rehberi](data-adapter/README.md), eğitim/doğrulama/test ayrımını ve dönüşümü sıfırdan açıklar. UR5 için fine-tuning ve öğrenilmiş kapalı çevrim politika henüz sonraki aşamadadır.

[15 Kasım kontrol notu](AUDIT-2026-11-15.md), doğrulanmış sonuçları ve sunucuda bekleyen kontrolleri ayırır. VALAR'da bu klasörden `bash status.sh` çalıştırarak son 14 gündeki proje işleri ile mevcut kuyruğu görebilirsin. Bu betik bir anlık durum sorgusudur; arka planda bildirim göndermez.

## 1. Koç kümesine bağlan

Ivanti'de **Koç VPN** bağlantısının **Connected** olduğunu kontrol et. Mac Terminal'de `KULLANICI` yerine sana atanan HPC kullanıcı adını yaz.

```bash
ssh KULLANICI@login.valar.ku.edu.tr
```

`hostname` komutu hangi makinede olduğunu gösterir. SSH oturumunu açtığın makine giriş düğümüdür. Burada dosya kopyalar ve işleri Slurm kuyruğuna gönderirsin. Modeli Slurm'un ayırdığı hesaplama düğümü çalıştırır. İlk girişte parola değiştirme ekranı çıkabilir. [Koç HPC giriş rehberi](https://help.ku.edu.tr/ithelp/how-do-i-login-to-the-hpc-clusters)

## 2. Projeyi scratch alanına aktar

VALAR'da işlerin çalıştığı kişisel `/scratch` dizinini giriş düğümünde kontrol et. Bu projede doğrulanan yol `/scratch/$USER`. Hesabına farklı bir yol verildiyse o yolu kullan.

```bash
ls -ld "/scratch/$USER"
```

Mac'te `vla-hpc` klasörünün bulunduğu üst klasöre geç ve yeni bir Terminal penceresinden kopyala. Burada `KULLANICI` hem SSH kullanıcı adı hem de örnek scratch yolundaki kullanıcı adıdır.

```bash
scp -r vla-hpc KULLANICI@login.valar.ku.edu.tr:/scratch/KULLANICI/
```

VALAR Terminal'inde çalışma alanına geç ve erişebildiğin Slurm kuyrukları ile GPU adlarına bak.

```bash
cd "/scratch/$USER/vla-hpc"
sacctmgr -n -P show assoc where user="$USER" format=Account,Partition,QOS
sinfo -o '%P %G'
```

`.runtime` içinde Python ortamı, kaynak depoları ve Hugging Face önbelleği oluşur. Model deposu yaklaşık 16 GB. Kurulum, önbellek ve videolar için ek boş alan gerekir. [Koç depolama rehberi](https://help.ku.edu.tr/ithelp/how-to-use-storage-home-folder-datasets-user-fil) · [Checkpoint dosyaları](https://huggingface.co/moojink/openvla-7b-oft-finetuned-libero-10/tree/main)

## 3. Ortamı kur ve ilk denemeyi çalıştır

Aşağıdaki kaynak seçimleri Koç'un `ai` kuyruğu ve `ampere_a40` GPU örneğine dayanır. `sacctmgr` farklı bir hesap veya QoS gösteriyorsa seçenekleri hesabına göre değiştir. Tek bir A40 48 GB ilk deneme için hedefimiz. İş ayarı, CUDA erişimini ve BF16 desteğini kullanmadan önce kontrol eder. [Koç Slurm örnekleri](https://help.ku.edu.tr/ithelp/how-do-i-write-and-submit-a-jobscript) · [Koç GPU örnekleri](https://help.ku.edu.tr/ithelp/how-do-i-interact-with-jobs-in-real-time)

Önce Python 3.10, PyTorch 2.2, OpenVLA-OFT ve LIBERO ortamını bir Slurm işi olarak kur. `prepare` aynı CPU işi içinde model dosyalarını da önbelleğe alır. Kurulum daha önce tamamlandıysa hazır ortamı kullanır.

```bash
sbatch --partition=ai --account=ai --qos=ai --time=36:00:00 job.slurm prepare
squeue -u "$USER"
```

Hazırlık işi `COMPLETED` olduktan sonra aşağıdaki iki işten birini gönder. `smoke`, bir GPU işlemi yapar ve LIBERO'dan iki kamera karesi kaydeder. `eval`, aynı kontrollerin ardından modeli çalıştırır. İlk değerlendirme için `eval` tek başına yeterli.

```bash
# Yalnızca GPU ve kamera kontrolü
sbatch --partition=ai --account=ai --qos=ai --gres=gpu:ampere_a40:1 job.slurm smoke

# Modelle LIBERO-10 değerlendirmesi
sbatch --partition=ai --account=ai --qos=ai --gres=gpu:ampere_a40:1 job.slurm eval
```

Her `sbatch` bir iş numarası verir. `IS_NO` yerine onu yaz.

```bash
sacct -j IS_NO --format=JobID,State,ExitCode,Elapsed
tail -n 40 slurm-vla-libero-IS_NO.out
```

`runs/IS_NO/` altında kamera kareleri, GPU bilgisi, kullanılan kaynak commit'leri ve paket sürümleri bulunur. Değerlendirme tamamlanınca `eval-logs/` altında başarı özeti, `rollouts/` altında MP4 videoları oluşur. Betik, değerlendirme günlüğünde 10 bölüm ve dosya sisteminde 10 dolu video görmeyi bekler. Bölüm içi bir yazılım hatası varsa işi başarısız sayar. Robotun bir görevi başaramaması ise değerlendirme sonucunun parçasıdır. Sonuçları saklamak için kişisel `/scratch` alanından dışarı kopyala. [OpenVLA-OFT LIBERO rehberi](https://github.com/moojink/openvla-oft/blob/main/LIBERO.md) · [Koç depolama rehberi](https://help.ku.edu.tr/ithelp/how-to-use-storage-home-folder-datasets-user-fil)
