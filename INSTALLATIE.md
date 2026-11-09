# SMARTY Energy voor Home Assistant — installatie (pilot)

Met deze integratie leest Home Assistant je energiedata **bij SMARTY** uit:
zonne-opwek, net, batterij, verbruik en de meetwaarden per apparaat. De
koppeling kan alleen lezen en niets aansturen. Home Assistant maakt dus géén
verbinding meer met je omvormer of batterij, en zit SMARTY niet meer in de weg.

Je hebt Home Assistant **2024.12 of nieuwer** nodig.

## 1. Token maken in SMARTY

1. Open de SMARTY-app of log in op **https://www.getsmarty.nl**.
2. Ga naar **Instellingen → Home Assistant**.
3. Geef de koppeling een naam (bijv. "Home Assistant thuis") en klik **Token maken**.
4. Kopieer de token meteen: hij is maar één keer zichtbaar. Kwijt? Trek hem in en maak een nieuwe.

## 2. Integratie in Home Assistant zetten (kies 1 van de 3 opties)

### Optie A: Via HACS (aanbevolen — geen zip uitpakken)

1. Open **HACS** in Home Assistant en klik rechtsboven op **⋮ → Aangepaste repositories** (*Custom repositories*).
2. Plak bij **Repository**: `https://github.com/verstraetenromanojarvis/smarty-home-assistant` en kies als type **Integratie** (*Integration*).
3. Zoek in HACS op **SMARTY Energy** en klik op **Downloaden**.
4. Herstart Home Assistant (**Instellingen → Systeem → Herstarten**).

### Optie B: Met 1 commando via Terminal & SSH (geen zip uitpakken)

Heb je geen HACS, maar wel de add-on **Terminal & SSH** in Home Assistant? Plak dan dit commando in de Terminal van Home Assistant:

```sh
mkdir -p /config/custom_components && curl -fsSL https://www.getsmarty.nl/api/v1/home-assistant/integration.zip -o /tmp/smarty.zip && unzip -qo /tmp/smarty.zip -d /config && rm /tmp/smarty.zip && ha core restart
```

Dit zet de bestanden automatisch in `/config/custom_components/smarty` en herstart Home Assistant.

### Optie C: Handmatig met dit zip-bestand

Kopieer de map `custom_components/smarty` uit deze zip naar de configuratiemap
van Home Assistant, zodat je dit krijgt:

```
config/
└── custom_components/
    └── smarty/
        ├── __init__.py
        ├── api.py
        ├── config_flow.py
        ├── const.py
        ├── manifest.json
        ├── sensor.py
        ├── strings.json
        └── translations/
```

Dat kan met de add-on **Studio Code Server** (map `smarty` erin slepen), via **Samba share**, of met **File editor**. Bestaat de map `custom_components` nog niet? Maak hem dan eerst aan.

Herstart daarna Home Assistant (**Instellingen → Systeem → Herstarten**).

## 3. Integratie toevoegen

1. **Instellingen → Apparaten en diensten → Integratie toevoegen**.
2. Zoek op **SMARTY Energy**.
3. Server: `https://www.getsmarty.nl` (staat al ingevuld). Token: plak je token.

Je krijgt een apparaat met de naam van je installatie, met onder andere:

| Sensor | Betekenis |
|---|---|
| Zonnevermogen | W, altijd positief |
| Netvermogen | W: **+ = afname, − = teruglevering** |
| Netafname / Netteruglevering | W, allebei positief |
| Batterijvermogen | W: **+ = ontladen, − = laden** |
| Batterij laadvermogen / ontlaadvermogen | W, allebei positief |
| Huisverbruik | W |
| Batterijlading | % |
| Datastatus | ok / deels actueel / verouderd |
| Strategie | bijv. Kostenoptimalisatie of Eigen verbruik |
| Kosten vandaag / Kosten deze maand | EUR: **+ = betaald, − = verdiend** |
| Geschat zelfverbruik vandaag | % |
| Noodstroom actief | Ja / Nee |

Daarnaast per apparaat (omvormer, batterij, slimme meter…) de beschikbare
meetwaarden, zoals tellerstanden in kWh, spanning en temperaturen. Bij een
batterij onder andere *Batterij geladen totaal*, *Batterij ontladen totaal*,
*Batterijcycli*, *Batterijgezondheid (SOH)*, *Batterijstatus*, *Bruikbare
capaciteit* en *Resterende energie*. Bij een omvormer met noodstroom (bijv. de
Pylontech FH3X) ook *Netstatus* (netgekoppeld of noodstroom),
*Omvormerstatus* en het *Noodstroomvermogen*.

Tijdens een stroomstoring zie je noodstroom alleen als de SMARTY-controller en
je internetverbinding zelf stroom houden (bijv. via de noodstroomgroep).

Is een meting ouder dan 2 minuten of fysiek onmogelijk (een storing in de
verbinding met het apparaat), dan toont Home Assistant die sensor even als
*niet beschikbaar* in plaats van een verkeerde waarde.

Home Assistant haalt elke 30 seconden nieuwe data op. Kosten en zelfverbruik
worden hooguit elke 10 minuten bijgewerkt.

## 4. Energie-dashboard instellen

Ga naar **Instellingen → Dashboards → Energie** en kies:

- **Elektriciteitsnet:** bij de *slimme meter* *Netafname totaal* (afname) en
  *Teruglevering totaal* (teruglevering). Vermogen (als erom gevraagd wordt):
  *Netvermogen* van je installatie, type **Standaard** (+ = afname).
- **Zonnepanelen:** bij je omvormer *Totale energie* (de levenslange teller).
  Vermogen: *Zonnevermogen* van je installatie.
- **Thuisbatterij:** energie uit de batterij = *Batterij ontladen totaal*,
  energie in de batterij = *Batterij geladen totaal*. Vermogen:
  *Batterijvermogen* van je installatie, type **Standaard** (+ = ontladen).
  Wordt er gevraagd om laadtoestand of capaciteit: *Batterijlading* en
  *Bruikbare capaciteit*.

Wijst de energiestroom de verkeerde kant op, kies dan *Omgekeerd* in plaats
van *Standaard*.

**Let op:** *Netafname totaal* en *Teruglevering totaal* bij je omvormer of
batterij (bijv. de Pylontech FH3X) zijn de netmeter-tellers van die omvormer,
**geen** batterij-energie. Gebruik die niet voor het net of de batterij.

*Kosten vandaag* en *Kosten deze maand* niet als kostensensor in het
Energie-dashboard invullen (dan telt teruglevering dubbel); gebruik ze in je
eigen kaarten.

## Bijwerken naar een nieuwe versie

- **Via HACS:** HACS meldt vanzelf wanneer er een update is. Klik op **Bijwerken** en herstart Home Assistant.
- **Via Terminal & SSH:** voer hetzelfde commando uit stap 2 opnieuw uit.
- **Handmatig:** download de nieuwe zip onder **Instellingen → Home Assistant**, vervang `config/custom_components/smarty` en herstart Home Assistant.

Je token, bestaande sensoren en hun geschiedenis blijven behouden; nieuwe
sensoren verschijnen vanzelf.

## Werkt het niet?

- **"Token ongeldig of ingetrokken"**: maak een nieuwe token in het portaal.
  Home Assistant vraagt je dan vanzelf om de nieuwe token.
- **Sensoren "niet beschikbaar"**: SMARTY heeft even geen verse meting van dat
  apparaat. Kijk in het SMARTY-portaal of het apparaat online is.
- Vragen of wensen? Reageer op onze e-mail. Dit is een pilot en jouw
  feedback bepaalt wat we verbeteren voordat de koppeling in de app komt.
