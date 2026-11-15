# PowerPlayer Linux 1.0 — DVD e Blu-ray (prima integrazione)

Basato sulla versione 0.9.1. Le funzioni video e la libreria Qt Multimedia sono invariate.

## Avvio

```bash
sudo pacman -S --needed mpv
cd ~/Scaricati/powerplayer-linux-1.0
python powerplayer.py
```

Seleziona **DVD / Blu-ray** nella barra laterale. Puoi aprire un lettore `/dev/sr0`, una cartella con `VIDEO_TS`/`BDMV` o un file ISO. Il disco si apre **in una finestra mpv separata**, non nell'area video di PowerPlayer. I comandi della finestra mpv sono quelli di mpv.

Questa è una prima integrazione, non un lettore Blu-ray completo: non garantisce menu DVD/Blu-ray, protezioni AACS/BD+, UHD o riproduzione di ogni ISO. Il lettore USB non è stato ancora collaudato. I dischi non protetti dipendono dai componenti mpv e dalle librerie disponibili.

La versione 0.9.1 non viene modificata.
