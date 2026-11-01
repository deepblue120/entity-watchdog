# Entity Watchdog

Eine Home Assistant Integration zur Überwachung von Geräten mithilfe von Zeitstempeln der letzten Meldung/Änderung einer Entität.

## Installation über HACS

1. HACS öffnen → Integrationen → Menü (⋮) → Benutzerdefinierte Repositories
2. URL eintragen: `https://github.com/deepblue120/entity-watchdog`
3. Kategorie: Integration
4. "Entity Watchdog" suchen und installieren
5. Home Assistant neu starten

## Manuelle Installation

Ordner `custom_components/entity_watchdog` in dein `config/custom_components/`-Verzeichnis kopieren und Home Assistant neu starten.

## Konfiguration

Über die HA-Oberfläche: Einstellungen → Geräte & Dienste → Integration hinzufügen → "Entity Watchdog" suchen.

### Sensoren hinzufügen

Über **Konfigurieren** am Integrationseintrag:

- **Sensor hinzufügen** – ein einzelnes Gerät wählen und anschließend die zu überwachende Entität.
- **Mehrere Geräte hinzufügen (nach Integration)** – eine Integration wählen (z. B. BTHome). Alle noch nicht überwachten Geräte dieser Integration erscheinen als Checkbox-Liste und sind bereits angehakt; nicht gewünschte einfach abwählen. Die Wartezeit gilt für alle ausgewählten Geräte.
  Die Entität wird pro Gerät automatisch gewählt: bevorzugt die Signalstärke (RSSI/LQI), sonst Temperatur oder Luftfeuchte. Geräte ohne passende (aktivierte) Entität werden übersprungen. Name und Entität lassen sich danach über **Sensor bearbeiten** anpassen.

### Batterie-Informationen (optional)

Beim Hinzufügen und Bearbeiten eines Sensors lassen sich zusätzlich Batterie-Daten hinterlegen. Daraus entstehen eigene Sensoren:

| Sensor | Beschreibung |
|---|---|
| `<Name> Batteriestand` | Wird automatisch aus der Batterie-Entität des Geräts übernommen (%). Die Entität wird beim Hinzufügen automatisch erkannt und kann überschrieben oder geleert werden. |
| `<Name> Batterietyp` | Per Dropdown gewählt (CR2032, AAA, AA, 9V, …). Eigene Typen können eingetippt werden. |
| `<Name> Batterieanzahl` | Anzahl der Batterien im Gerät. |

Batteriestand gibt es nur, wenn eine Batterie-Entität gesetzt ist; Typ und Anzahl nur, wenn ein Typ gewählt wurde. Beim Mehrfach-Hinzufügen wird die Batterie-Entität je Gerät automatisch erkannt, Typ und Anzahl gelten für alle ausgewählten Geräte.

Alle Entitäten eines Watchers (überfällig, zuletzt gesehen, Batterie) sind seit Version 2.5.0 einem gemeinsamen Gerät mit dem Namen des Watchers zugeordnet.

> Tipp für BTHome: Die Signalstärke-Entität ist dort oft standardmäßig deaktiviert. Wer sie vorher aktiviert, bekommt die zuverlässigste Überwachung, da sie sich bei nahezu jeder Meldung ändert.
