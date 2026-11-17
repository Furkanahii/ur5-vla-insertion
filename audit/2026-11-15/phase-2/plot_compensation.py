"""Compare real recordings with gravity enabled and unchanged PD gains."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

base=Path(__file__).resolve().parents[3]/'ur5-pilot'/'runs'
fig,axes=plt.subplots(2,1,figsize=(9,6),sharex=True,constrained_layout=True)
for run_id,label,color in [('2025274_4','Ağırlık telafisi kapalı','#3265a8'),('2025430','Ağırlık telafisi açık','#e58324')]:
    rows=[json.loads(line) for line in (base/run_id/'steps.jsonl').read_text().splitlines()]
    time=[row['time_s'] for row in rows]
    for axis,plot in zip([0,2],axes):
        values=[1000*(row['wrist_position_base_m'][axis]-row['target_position_base_m'][axis]) for row in rows]
        plot.plot(time,values,label=label,color=color,linewidth=2)
for plot,axis in zip(axes,['X','Z']):
    plot.axhline(0,color='#737a82',linewidth=.7)
    plot.set_ylabel(f'{axis} hedef hatası (mm)')
    plot.grid(alpha=.2)
axes[0].legend(loc='lower right')
axes[1].set_xlabel('Simülasyon süresi (s), 20 Hz ölçüm')
fig.suptitle('UR5 hareket takibi — iki koşulda da yerçekimi açık')
fig.savefig(Path(__file__).with_name('gravity-compensation.png'),dpi=160)
