# GHL ProfiLux für Home Assistant

Liest einen GHL ProfiLux 4 über die lokale GHL-API (TCP, Port 10002) aus. Nur lesend, keine Cloud.

## Voraussetzungen

- ProfiLux 4 mit Firmware **7.52 oder neuer**, WLAN-Modul 7141 oder neuer
- Am Gerät: **System → GHL API** einschalten (für diese Integration reicht „nur lesen")
- Die API steht nach jedem Firmware-Update wieder auf „aus"
- Der Port bedient nur einen Client gleichzeitig. Die Integration verbindet pro Abfrage kurz und schließt wieder, damit GHL Connect nicht blockiert wird.

## Installation über HACS

1. HACS → ⋮ → *Benutzerdefinierte Repositories* → dieses Repository, Kategorie *Integration*
2. Installieren, Home Assistant neu starten
3. *Einstellungen → Geräte & Dienste → Integration hinzufügen → GHL ProfiLux*, IP-Adresse eintragen

## Was angezeigt wird

| Art | Entities |
|---|---|
| Sensoren | Temperatur, pH, Redox, Leitwert (Leitwert standardmäßig aus) |
| Schaltkanäle | Zustand (an/aus) und Strom in A, pro benanntem Kanal |
| Dosierer | Füllstand in ml, Kapazität und Prozent als Attribute |
| Pegel | Pegelsensoren (nur Sensor 1 standardmäßig aktiv) |
| KH Director | KH-Wert, nicht verfügbar solange das Gerät nicht antwortet |

Die Zuordnung der Sensoren zu Temperatur/pH/Redox/Leitwert (Index 0 bis 3) ist in `sensor.py` festgelegt, weil die API den Sensortyp nicht liefert. Hat ein Sensor in GHL einen Namen, wird dieser verwendet.

## Grenzen

- Die GHL-API schaltet **keine Ausgänge**. Schaltkanäle sind nur lesbar.
- Wasserwechsel, Wartung und Futterpause lassen sich laut GHL per API starten. Das ist noch nicht eingebaut und braucht am Gerät Vollzugriff.
- Namen kommen im Windows-Zeichensatz (Umlaute) vom Gerät und werden entsprechend gelesen.
- Abfrage alle 60 Sekunden. Die erste Erkennung der Geräte-Ressourcen beim Start dauert etwas länger.
