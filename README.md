# SMARTY Energy voor Home Assistant

Alleen-lezen koppeling tussen SMARTY en Home Assistant. Home Assistant leest
zonne-opwek, net, batterij, verbruik en per-apparaat meetwaarden **bij SMARTY**
uit. De koppeling kan niets aansturen.

> **Koppel Home Assistant niet rechtstreeks via Modbus aan je omvormer of
> batterij.** Veel apparaten (o.a. de Pylontech FH3X) accepteren maar één
> Modbus-verbinding tegelijk. Een tweede verbinding vanuit Home Assistant
> verdringt de SMARTY-controller, waardoor je batterij niet meer uitgelezen of
> gestuurd kan worden. Verwijder een bestaande Modbus-integratie naar die
> apparaten voordat je deze koppeling gebruikt.

## 1. Token maken

In de SMARTY-app: **Instellingen → Home Assistant → Token maken**. Kopieer de
token direct; hij is maar één keer zichtbaar. Je kunt tokens daar ook weer
intrekken.

## 2a. Integratie installeren (aanbevolen)

- **Via HACS (aanbevolen):** ga in Home Assistant naar *HACS → ⋮ → Aangepaste repositories* (*Custom repositories*), voeg `https://github.com/verstraetenromanojarvis/smarty-home-assistant` toe met type **Integratie** (*Integration*), installeer **SMARTY Energy** en herstart Home Assistant.
- **Via Terminal & SSH (1 commando):** plak in de Home Assistant Terminal:
  ```sh
  mkdir -p /config/custom_components && curl -fsSL https://www.getsmarty.nl/api/v1/home-assistant/integration.zip -o /tmp/smarty.zip && unzip -qo /tmp/smarty.zip -d /config && rm /tmp/smarty.zip && ha core restart
  ```
- **Handmatig:** kopieer `custom_components/smarty` naar `<config>/custom_components/smarty` en herstart Home Assistant.

Daarna: *Instellingen → Apparaten en diensten → Integratie toevoegen → SMARTY
Energy*. Vul de server (`https://www.getsmarty.nl`) en de token in.

Je krijgt:

| Sensor | Betekenis |
|---|---|
| Zonnevermogen | W, altijd positief |
| Netvermogen | W, **+ = afname, − = teruglevering** |
| Netafname / Netteruglevering | W, beide positief |
| Batterijvermogen | W, **+ = ontladen, − = laden** |
| Batterij laad-/ontlaadvermogen | W, beide positief |
| Huisverbruik, Laadpaal, Warmtepomp | W |
| Batterijlading | %, capaciteit-gewogen gemiddelde |
| Datastatus | `ok`, `partial`, `stale`, `no_devices` |
| Strategie | Eigen verbruik, Kostenoptimalisatie, Peak shaving, Geen aansturing, … |
| Kosten vandaag / Kosten deze maand | EUR, **+ = betaald, − = verdiend** (zelfde berekening als *Verdiensten* in de app) |
| Geschat zelfverbruik vandaag | % |
| Noodstroom actief | Ja / Nee: *Ja* zodra een omvormer het huis uit zijn noodstroomuitgang voedt omdat het net weg is |

Plus per apparaat de beschikbare meetwaarden (vermogen, tellerstanden in kWh,
temperaturen, spanning…). Bij een batterij ook: *Batterij geladen totaal* /
*Batterij ontladen totaal* (kWh), *Batterijcycli*, *Batterijgezondheid (SOH)*,
*Batterijspanning*, *Batterijstroom*, *Batterijstatus* (laden, ontladen,
stand-by, slaap, storing), *Bruikbare capaciteit* (capaciteit × SOH) en
*Resterende energie* (van het batterijmanagement, anders capaciteit × lading).
Bij een omvormer met noodstroom (bijv. de Pylontech FH3X) ook: *Netstatus*
(netgekoppeld of noodstroom), *Omvormerstatus* (wachten, normaal, storing),
*Noodstroomvermogen* (W), *Noodstroomspanning*, *Noodstroomfrequentie* en
*Noodstroom-energie totaal* (kWh).

Noodstroom zie je alleen als de SMARTY-controller en je internetverbinding
tijdens de stroomstoring zelf stroom houden (bijv. aangesloten op de
noodstroomgroep). Zonder verse meting is *Noodstroom actief* *niet
beschikbaar*, nooit *Nee*.

Meetwaarden ouder dan 2 minuten worden als *niet beschikbaar* getoond in
plaats van als actuele waarde. Dat geldt ook voor fysiek onmogelijke waarden
(bijv. een netfrequentie van 576 Hz door een storing in de Modbus-gateway) en
voor een tellerstand die één keer onverklaarbaar daalt of verspringt: zo komt
zo'n uitschieter nooit in je grafieken of in het Energie-dashboard. Kosten en
zelfverbruik worden hooguit elke 10 minuten herberekend; zijn prijzen of
metingen onvolledig, dan is de sensor *niet beschikbaar* (nooit € 0).

Home Assistant vraagt elke 30 seconden data op. SMARTY staat maximaal
12 verzoeken per minuut per token toe.

### Energie-dashboard instellen

*Instellingen → Dashboards → Energie*:

| Onderdeel | Energie (kWh-teller) | Vermogen (W), als je versie erom vraagt |
|---|---|---|
| Elektriciteitsnet | Slimme meter: *Netafname totaal* (afname) en *Teruglevering totaal* (teruglevering) | *Netvermogen* van je installatie, type **Standaard** (+ = afname) |
| Zonnepanelen | Omvormer: *Totale energie* (de levenslange teller, niet *Energie vandaag*) | *Zonnevermogen* van je installatie |
| Thuisbatterij | *Batterij ontladen totaal* (energie uit de batterij) en *Batterij geladen totaal* (energie in de batterij) | *Batterijvermogen* van je installatie, type **Standaard** (+ = ontladen) |

Vraagt je versie bij de batterij om laadtoestand of capaciteit, kies dan
*Batterijlading* (%) en *Bruikbare capaciteit* (kWh). SMARTY gebruikt voor net
en batterij dezelfde tekens als de optie *Standaard* van Home Assistant; wijst
de energiestroom toch de verkeerde kant op, kies dan *Omgekeerd*.

> **Let op:** *Netafname totaal* en *Teruglevering totaal* bij je omvormer of
> batterij (bijv. de Pylontech FH3X) zijn de eigen netmeter-tellers van die
> omvormer, **geen** batterij-energie. Gebruik voor het net de tellers van je
> slimme meter en voor de batterij *Batterij geladen/ontladen totaal*.

*Kosten vandaag* en *Kosten deze maand* zijn het nettoresultaat (inkoop min
teruglevering) zoals SMARTY dat berekent. Vul ze niet in als kostensensor in
het Energie-dashboard (dat telt teruglevering apart en zou dubbel tellen);
gebruik ze in je eigen kaarten of automatiseringen.

Heeft een apparaat geen kWh-teller, maak dan een *Integraal*-helper
(Riemann-som) op de vermogenssensor.

## 2b. Zonder integratie: REST-sensor

```yaml
# configuration.yaml — token in secrets.yaml: smarty_token: "Bearer smha_…"
rest:
  - resource: https://www.getsmarty.nl/api/v1/home-assistant/state
    scan_interval: 30
    headers:
      Authorization: !secret smarty_token
    sensor:
      - name: SMARTY zonnevermogen
        value_template: "{{ value_json.power.solar_w }}"
        unit_of_measurement: W
        device_class: power
        state_class: measurement
      - name: SMARTY netvermogen
        value_template: "{{ value_json.power.grid_w }}"
        unit_of_measurement: W
        device_class: power
        state_class: measurement
      - name: SMARTY batterijvermogen
        value_template: "{{ value_json.power.battery_w }}"
        unit_of_measurement: W
        device_class: power
        state_class: measurement
      - name: SMARTY huisverbruik
        value_template: "{{ value_json.power.home_w }}"
        unit_of_measurement: W
        device_class: power
        state_class: measurement
      - name: SMARTY batterijlading
        value_template: "{{ value_json.battery_soc_pct }}"
        unit_of_measurement: "%"
        device_class: battery
        state_class: measurement
```

## API

`GET /api/v1/home-assistant/state` met `Authorization: Bearer smha_…`.
De token is gekoppeld aan één gebruiker en één installatie, geeft géén toegang
tot andere SMARTY-endpoints en werkt niet meer zodra hij wordt ingetrokken of de
gebruiker de toegang tot de installatie verliest. Het endpoint leest alleen de
laatst bekende meetwaarden uit de SMARTY-cache; het maakt nooit zelf verbinding
met je apparaten.

Sinds schema 1.1 (`schema_minor: 1`, alleen toevoegingen) bevat het antwoord
ook `ems_mode` (strategie, bijv. `cost_minimization`), per apparaat `states`
(`battery_status`: `charging`, `discharging`, `standby`, `sleep`, `fault`) en
een blok `finance` met `today` en `month` (`result_eur`: + = verdiend,
`cost_eur`: + = betaald, `since`: begin van de periode) en
`self_consumption_pct`. Onbekende waarden zijn `null`, nooit 0.

Sinds schema 1.2 (`schema_minor: 2`, alleen toevoegingen) bevat het antwoord
`backup_active` (`true` zodra een apparaat met een verse meting op noodstroom
draait, `false` als alle melders netgekoppeld zijn, `null` als geen enkel
apparaat het meldt), per apparaat in `states` ook `grid_mode` (`on_grid`,
`backup`) en `inverter_state` (`wait`, `normal`, `fault`) en in `fields` de
noodstroomwaarden `eps_power_w`, `eps_voltage_v`, `eps_frequency_hz` en
`eps_output_total_kwh`.
