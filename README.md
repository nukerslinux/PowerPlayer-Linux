# PowerPlayer Linux 1.0

**PowerPlayer Linux** è un lettore multimediale per Linux sviluppato in Python e PyQt6, con un'interfaccia grafica personalizzata e uno sfondo a cielo stellato.

## Funzionalità

- Riproduzione di video MP4 e MKV tramite Qt Multimedia.
- Libreria multimediale e navigazione tra i file.
- Ripresa della riproduzione dall'ultima posizione salvata.
- Controlli multimediali integrati.
- Supporto preliminare a DVD e Blu-ray tramite mpv.
- Interfaccia grafica dedicata.

## Download

È disponibile una versione **AppImage per Linux x86_64**.

[Scarica PowerPlayer Linux 1.0 AppImage](https://github.com/nukerslinux/PowerPlayer-Linux/releases/download/v1.0.0/PowerPlayer-Linux-1.0-x86_64.AppImage)

## Avvio dell'AppImage

Dopo aver scaricato il file, apri un terminale nella cartella in cui si trova ed esegui:

```bash
chmod +x PowerPlayer-Linux-1.0-x86_64.AppImage
./PowerPlayer-Linux-1.0-x86_64.AppImage
```

Non è necessario installare manualmente Python o PyQt6 per avviare l'AppImage.

La compatibilità con altre distribuzioni Linux è ancora da verificare.

## Avvio dal codice sorgente

Per eseguire direttamente il programma Python, installa PyQt6 e avvia:

```bash
python powerplayer.py
```

## DVD e Blu-ray

PowerPlayer include una prima integrazione per DVD e Blu-ray.

È possibile selezionare un lettore ottico, ad esempio `/dev/sr0`, una cartella `VIDEO_TS` o `BDMV`, oppure un file ISO.

La riproduzione viene avviata tramite **mpv in una finestra separata**, utilizzando i controlli di mpv.

Per questa funzione è necessario che mpv sia installato sul sistema.

Su Arch Linux e Garuda Linux:

```bash
sudo pacman -S --needed mpv
```

Il supporto ai dischi ottici è ancora sperimentale e non è stato completamente verificato con dischi fisici.

## Versione

**1.0.0** — Prima versione pubblica.

## Sviluppo

Progetto open source ospitato su GitHub.

[Repository PowerPlayer Linux](https://github.com/nukerslinux/PowerPlayer-Linux)
