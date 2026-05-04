#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import random
import math
from math import ceil

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()


parametri = {
    # Lotto iniziale
    "min_es": 220,
    "max_es": 420,
    "peso_medio_min": 1.2,
    "peso_medio_max": 1.8,

    # Quote di destinazione
    "quota_f_min": 0.12,
    "quota_f_max": 0.22,
    "quota_fil_min": 0.45,
    "quota_fil_max": 0.65,

    # Rese di lavorazione
    "resa_evisc": 0.88,
    "resa_filetti": 0.55,
    "resa_uova": 0.10,

    # Resa uova casuale (attualmente non attiva)
    "usa_resa_uova_casuale": False,
    "resa_uova_min": 0.08,
    "resa_uova_max": 0.12,

    # Confezione uova (100 g)
    "peso_vas": 0.10,

    # Capacità operative (unità/ora)
    "cap_ps": 120.0,              # esemplari/ora
    "cap_ev": 85.0,               # esemplari/ora
    "cap_lfu_filetti": 38.0,      # esemplari/ora
    "cap_lfu_uova": 48.0,         # esemplari/ora
    "cap_cf_trota": 170.0,        # kg/ora
    "cap_cf_filetti": 110.0,      # kg/ora
    "cap_cf_uova": 150.0,         # vasetti/ora

    # Durata del turno (minuti)
    "turno_min": 480.0,
}

# Priorità di servizio sulle risorse condivise
PRIO_PS =["uova_trota", "filetti_freschi", "trota_eviscerata"]
PRIO_LFU =["uova_trota", "filetti_freschi"]
PRIO_CF =["uova_trota", "filetti_freschi", "trota_eviscerata"]

LINEE =["trota_eviscerata", "filetti_freschi", "uova_trota"]
RISORSE =["ps", "ev", "lfu", "cf"]
RISORSE_COMUNI =["ps", "lfu", "cf"]



# CLASSI DATI

class Lotto:
    """Dati del lotto generato casualmente."""
    def __init__(self, tot, peso_medio, quota_femmine, quota_filetti, resa_uova):
        self.tot = tot
        self.peso_medio = peso_medio
        self.peso_vivo_tot = round(tot * peso_medio, 3)
        self.quota_femmine = quota_femmine
        self.quota_filetti = quota_filetti
        self.resa_uova = resa_uova
        self.uova_trota = 0
        self.filetti_freschi = 0
        self.trota_eviscerata = 0


class OutLinea:
    """Quantità e tempi per una linea produttiva."""
    def __init__(self, tipo, es, p_vivo, p_out, vasetti=0):
        self.tipo = tipo
        self.nome = nome_linea(tipo)
        self.es = es
        self.p_vivo = p_vivo
        self.p_out = p_out
        self.vasetti = vasetti

        # Tempi, calcolati dopo la schedulazione
        self.attivo = 0.0
        self.att_ps = 0.0
        self.att_lfu = 0.0
        self.att_cf = 0.0
        self.att_tot = 0.0
        self.fine = 0.0


class Fase:
    """Una fase di lavorazione su una risorsa."""
    def __init__(self, linea, nome, risorsa, durata, ready, ordine=0):
        self.linea = linea
        self.nome = nome
        self.risorsa = risorsa
        self.durata = durata
        self.ready = ready
        self.ordine = ordine
        self.inizio = 0.0
        self.fine = 0.0
        self.attesa = 0.0


class Risultato:
    """Contenitore finale della simulazione."""
    def __init__(self, scenario, seed, config, lotto, output_linee, durate, piani,
                 statistiche, tempo_totale, sforamento, collo_bottiglia):
        self.scenario = scenario
        self.seed = seed
        self.config = config
        self.lotto = lotto
        self.output_linee = output_linee
        self.durate = durate
        self.piani = piani
        self.statistiche = statistiche
        self.tempo_totale = tempo_totale
        self.sforamento = sforamento
        self.collo_bottiglia = collo_bottiglia




def crea_config(**modifiche):
    """Restituisce una copia dei parametri base con le modifiche richieste."""
    config = parametri.copy()
    config.update(modifiche)
    return config


def nome_linea(t):
    if t == "trota_eviscerata":
        return "Trota intera eviscerata"
    if t == "filetti_freschi":
        return "Filetti freschi di trota"
    return "Uova di trota selezionate e confezionate"


def nome_risorsa(r):
    if r == "ps":
        return "PS - Prelievo e smistamento"
    if r == "ev":
        return "EV - Banco eviscerazione"
    if r == "lfu":
        return "LFU - Lavorazione Filetti e Uova"
    if r == "cf":
        return "CF - Confezionatrice"
    return r


def abbreviazione_risorsa(r):
    if r == "ps":
        return "PS"
    if r == "ev":
        return "EV"
    if r == "lfu":
        return "LFU"
    if r == "cf":
        return "CF"
    return r.upper()


def minuti(quantita, capacita_ora):
    """Calcola la durata di una lavorazione in minuti."""
    if capacita_ora <= 0:
        raise ValueError("La capacità oraria deve essere positiva")
    return (quantita / capacita_ora) * 60.0


def formatta_tempo(minuti_tot):
    """Formatta i minuti nel formato 'Xh YYm'."""
    m = int(round(minuti_tot))
    return f"{m // 60}h {m % 60:02d}m"


def ritmo_operativo(capacita, unita="esemplari"):
    """Calcola il ritmo (secondi o minuti per unità) a partire dalla capacità oraria."""
    if capacita <= 0:
        return "N/A"
    if unita == "esemplari":
        sec = 3600.0 / capacita
        if sec < 60:
            return f"{capacita:.0f} es/ora (1 ogni {sec:.0f} sec)"
        else:
            return f"{capacita:.0f} es/ora (1 ogni {sec/60:.1f} min)"
    elif unita == "kg":
        min_kg = 60.0 / capacita
        return f"{capacita:.0f} kg/ora (1 kg ogni {min_kg:.1f} min)"
    elif unita == "vasetti":
        sec = 3600.0 / capacita
        if sec < 60:
            return f"{capacita:.0f} vas/ora (1 ogni {sec:.0f} sec)"
        else:
            return f"{capacita:.0f} vas/ora (1 ogni {sec/60:.1f} min)"
    return f"{capacita} /ora"


def trova_fase(piano, linea):
    """Recupera la fase di una linea dal piano di una risorsa."""
    for fase in piano:
        if fase.linea == linea:
            return fase
    raise ValueError(f"Linea {linea} non presente nel piano")


def controlla_parametri(config):
    """Verifiche di base per evitare configurazioni errate."""
    if config["min_es"] < 3:
        raise ValueError("Il lotto minimo deve essere almeno 3 esemplari")
    if config["min_es"] > config["max_es"]:
        raise ValueError("min_es non può superare max_es")
    if config["peso_medio_min"] > config["peso_medio_max"]:
        raise ValueError("Peso medio minimo > massimo")
    if config["quota_f_min"] > config["quota_f_max"]:
        raise ValueError("Quote femmine invertite")
    if config["quota_fil_min"] > config["quota_fil_max"]:
        raise ValueError("Quote filetti invertite")
    if config["resa_uova_min"] > config["resa_uova_max"]:
        raise ValueError("Resa uova minima > massima")



def genera_lotto(config, seed=None):
    """
    Genera un lotto casuale con ripartizione vincolata.
    Il procedimento assicura che tutte e tre le linee ricevano almeno un
    esemplare e che il totale degli esemplari torni esattamente.
    """
    rng = random.Random(seed)
    esemplari_totali = rng.randint(config["min_es"], config["max_es"])
    peso = round(rng.uniform(config["peso_medio_min"], config["peso_medio_max"]), 3)

    quota_femmine = round(rng.uniform(config["quota_f_min"], config["quota_f_max"]), 4)
    quota_filetti = round(rng.uniform(config["quota_fil_min"], config["quota_fil_max"]), 4)

    if config["usa_resa_uova_casuale"]:
        resa_uova = round(rng.uniform(config["resa_uova_min"], config["resa_uova_max"]), 4)
    else:
        resa_uova = config["resa_uova"]

    # Assegnazione uova (prima perché linea più delicata)
    uova_trota_grezzo = int(round(esemplari_totali * quota_femmine))
    uova_trota = max(1, min(uova_trota_grezzo, esemplari_totali - 2))

    # Assegnazione filetti sul residuo
    residuo = esemplari_totali - uova_trota
    filetti_freschi_grezzo = int(round(residuo * quota_filetti))
    filetti_freschi = max(1, min(filetti_freschi_grezzo, residuo - 1))

    # La trota eviscerata assorbe gli esemplari rimanenti
    trota_eviscerata = esemplari_totali - uova_trota - filetti_freschi

    if min(uova_trota, filetti_freschi, trota_eviscerata) < 1:
        raise ValueError("Ripartizione non valida: una linea è vuota")

    lotto = Lotto(esemplari_totali, peso, quota_femmine, quota_filetti, resa_uova)
    lotto.uova_trota = uova_trota
    lotto.filetti_freschi = filetti_freschi
    lotto.trota_eviscerata = trota_eviscerata
    return lotto



def calcola_output(lotto, config):
    """Determina i chilogrammi finali e il numero di vasetti."""
    vivo_trota = round(lotto.trota_eviscerata * lotto.peso_medio, 3)
    vivo_filetti = round(lotto.filetti_freschi * lotto.peso_medio, 3)
    vivo_uova = round(lotto.uova_trota * lotto.peso_medio, 3)

    kg_trota = round(vivo_trota * config["resa_evisc"], 3)
    kg_filetti = round(vivo_filetti * config["resa_filetti"], 3)
    kg_uova = round(vivo_uova * lotto.resa_uova, 3)

    vasetti = ceil(kg_uova / config["peso_vas"])

    output_linee = {
        "trota_eviscerata": OutLinea("trota_eviscerata", lotto.trota_eviscerata, vivo_trota, kg_trota),
        "filetti_freschi": OutLinea("filetti_freschi", lotto.filetti_freschi, vivo_filetti, kg_filetti),
        "uova_trota": OutLinea("uova_trota", lotto.uova_trota, vivo_uova, kg_uova, vasetti),
    }
    return output_linee



def calcola_durate(output_linee, config):
    """Converte le quantità in minuti di occupazione per ogni fase."""

    t = output_linee["trota_eviscerata"]
    f = output_linee["filetti_freschi"]
    u = output_linee["uova_trota"]

    durate = {}
    durate["trota_eviscerata"] = {
        "prelievo_smistamento": minuti(t.es, config["cap_ps"]),
        "eviscerazione": minuti(t.es, config["cap_ev"]),
        "confezionamento": minuti(t.p_out, config["cap_cf_trota"]),
    }
    durate["filetti_freschi"] = {
        "prelievo_smistamento": minuti(f.es, config["cap_ps"]),
        "filettatura": minuti(f.es, config["cap_lfu_filetti"]),
        "confezionamento": minuti(f.p_out, config["cap_cf_filetti"]),
    }
    durate["uova_trota"] = {
        "selezione_femmine": minuti(u.es, config["cap_ps"]),
        "lavorazione_uova": minuti(u.es, config["cap_lfu_uova"]),
        "confezionamento_vasetti": minuti(u.vasetti, config["cap_cf_uova"]),
    }
    return durate



def pianifica_risorsa(risorsa, fasi_da_fare, ordine_linee, criterio="priorita", start=0.0):
    """
    Gestisce l'accesso a una risorsa condivisa.
    Due criteri possibili:
      - priorita: vince la linea con priorità più alta (indice minore)
      - fifo: vince chi è pronto prima, con priorità in caso di parità
    """
    prior = {}
    for i, lin in enumerate(ordine_linee):
        prior[lin] = i

    da_fare = list(fasi_da_fare)
    fatte =[]
    t = start

    while da_fare:
        pronte =[fase for fase in da_fare if math.isclose(fase.ready, t, abs_tol=1e-9) or fase.ready <= t]
        if not pronte:
            t = min(fase.ready for fase in da_fare)
            pronte =[fase for fase in da_fare if math.isclose(fase.ready, t, abs_tol=1e-9) or fase.ready <= t]

        if criterio == "priorita":
            scelta = min(pronte, key=lambda fase: (prior.get(fase.linea, 999), fase.ready, fase.ordine))
        else:  # fifo
            scelta = min(pronte, key=lambda fase: (fase.ready, prior.get(fase.linea, 999), fase.ordine))

        da_fare.remove(scelta)

        scelta.risorsa = risorsa
        scelta.inizio = max(t, scelta.ready)
        scelta.attesa = scelta.inizio - scelta.ready
        scelta.fine = scelta.inizio + scelta.durata
        fatte.append(scelta)
        t = scelta.fine

    return fatte


def calcola_stat(piani, tempo_totale, config):
    """Calcola occupazione e percentuali di utilizzo per ogni risorsa."""
    statistiche = {}
    for ris, fasi in piani.items():
        occup = sum(fase.durata for fase in fasi)
        fine_max = max((fase.fine for fase in fasi), default=0.0)
        util_lotto = (occup / tempo_totale * 100.0) if tempo_totale > 0 else 0.0
        util_turno = occup / config["turno_min"] * 100.0
        statistiche[ris] = {
            "occupato": occup,
            "fine_max": fine_max,
            "util_lotto": util_lotto,
            "util_turno": util_turno,
        }
    return statistiche



def simula(config=None, seed=None, scenario="Scenario base"):
    """
    Esegue tutti i passi della simulazione:
    1. lotto -> 2. output -> 3. durate -> 4. schedulazione -> 5. statistiche
    """
    if config is None:
        config = crea_config()

    controlla_parametri(config)

    lotto = genera_lotto(config, seed)
    output_linee = calcola_output(lotto, config)
    durate = calcola_durate(output_linee, config)

    # PS: Prelievo e smistamento 
    fasi_ps =[
        Fase("uova_trota", "selezione_femmine", "ps", durate["uova_trota"]["selezione_femmine"], 0.0, ordine=1),
        Fase("filetti_freschi", "prelievo_smistamento", "ps", durate["filetti_freschi"]["prelievo_smistamento"], 0.0, ordine=2),
        Fase("trota_eviscerata", "prelievo_smistamento", "ps", durate["trota_eviscerata"]["prelievo_smistamento"], 0.0, ordine=3),
    ]
    piano_ps = pianifica_risorsa("ps", fasi_ps, PRIO_PS, "priorita")
    fine_ps = {fase.linea: fase.fine for fase in piano_ps}

    #  EV: Banco eviscerazione (solo trota eviscerata) 
    eviscerazione = Fase(
        "trota_eviscerata",
        "eviscerazione",
        "ev",
        durate["trota_eviscerata"]["eviscerazione"],
        fine_ps["trota_eviscerata"],
        ordine=1,
    )
    eviscerazione.inizio = eviscerazione.ready
    eviscerazione.fine = eviscerazione.inizio + eviscerazione.durata
    eviscerazione.attesa = 0.0
    piano_ev = [eviscerazione]

    # LFU: Lavorazione Filetti e Uova 
    fasi_lfu =[
        Fase("uova_trota", "lavorazione_uova", "lfu", durate["uova_trota"]["lavorazione_uova"], fine_ps["uova_trota"], ordine=1),
        Fase("filetti_freschi", "filettatura", "lfu", durate["filetti_freschi"]["filettatura"], fine_ps["filetti_freschi"], ordine=2),
    ]
    piano_lfu = pianifica_risorsa("lfu", fasi_lfu, PRIO_LFU, "priorita")
    fine_lfu = {fase.linea: fase.fine for fase in piano_lfu}

    # CF: Confezionatrice
    fasi_cf =[
        Fase("uova_trota", "confezionamento_vasetti", "cf", durate["uova_trota"]["confezionamento_vasetti"], fine_lfu["uova_trota"], ordine=1),
        Fase("filetti_freschi", "confezionamento", "cf", durate["filetti_freschi"]["confezionamento"], fine_lfu["filetti_freschi"], ordine=2),
        Fase("trota_eviscerata", "confezionamento", "cf", durate["trota_eviscerata"]["confezionamento"], eviscerazione.fine, ordine=3),
    ]
    piano_cf = pianifica_risorsa("cf", fasi_cf, PRIO_CF, "fifo")
    fine_cf = {fase.linea: fase.fine for fase in piano_cf}

    # Aggiornamento tempi output
    for lin in LINEE:
        out_linea = output_linee[lin]
        fase_ps = trova_fase(piano_ps, lin)
        fase_cf = trova_fase(piano_cf, lin)
        out_linea.att_ps = fase_ps.attesa
        out_linea.att_cf = fase_cf.attesa

        if lin in ("uova_trota", "filetti_freschi"):
            fase_lfu = trova_fase(piano_lfu, lin)
            out_linea.att_lfu = fase_lfu.attesa
        else:
            out_linea.att_lfu = 0.0

        out_linea.attivo = sum(durate[lin].values())
        out_linea.att_tot = out_linea.att_ps + out_linea.att_lfu + out_linea.att_cf
        out_linea.fine = fine_cf[lin]

    tempo_totale = max(fine_cf.values())
    sforamento = max(0.0, tempo_totale - config["turno_min"])

    piani = {
        "ps": piano_ps,
        "ev": piano_ev,
        "lfu": piano_lfu,
        "cf": piano_cf,
    }

    statistiche = calcola_stat(piani, tempo_totale, config)

    collo_bottiglia = max(RISORSE_COMUNI, key=lambda r: statistiche[r]["util_lotto"])

    return Risultato(
        scenario, seed, config, lotto, output_linee, durate, piani,
        statistiche, tempo_totale, sforamento, collo_bottiglia
    )



def stampa_report(risultato):
    lot = risultato.lotto
    console.print()
    console.print(Panel.fit(
        f"[bold cyan]SIMULAZIONE[/]\n"
        f"Scenario: [yellow]{risultato.scenario}[/]\n"
        f"Azienda: Rio Freddo Troticoltura S.r.l.\n"
        f"Seed: {risultato.seed if risultato.seed is not None else 'casuale'}",
        border_style="cyan"
    ))

    # 1. Lotto
    tab1 = Table(title="1. Lotto generato", box=box.SIMPLE, title_style="bold underline")
    tab1.add_column("Parametro", style="gold1", width=34)
    tab1.add_column("Valore", style="white")
    tab1.add_row("Esemplari totali", str(lot.tot))
    tab1.add_row("Peso medio", f"{lot.peso_medio:.3f} kg")
    tab1.add_row("Peso vivo totale", f"{lot.peso_vivo_tot:.2f} kg")
    tab1.add_row("Quota femmine", f"{lot.quota_femmine * 100:.2f}%")
    tab1.add_row("Quota filetti (sul residuo)", f"{lot.quota_filetti * 100:.2f}%")
    tab1.add_row("Resa uova effettiva", f"{lot.resa_uova * 100:.2f}%")
    tab1.add_row(
        "Ripartizione",
        f"uova_trota={lot.uova_trota}, filetti_freschi={lot.filetti_freschi}, trota_eviscerata={lot.trota_eviscerata}"
    )
    console.print(tab1)

    # 2. Parametri operativi e rese 
    tab2 = Table(title="2. Parametri operativi e Rese", box=box.SIMPLE, title_style="bold underline")
    tab2.add_column("Fase / Prodotto", style="gold1", width=34)
    tab2.add_column("Valore", style="white")
    tab2.add_row("Prelievo e smistamento (PS)", ritmo_operativo(risultato.config["cap_ps"], "esemplari"))
    tab2.add_row("Eviscerazione (EV)", ritmo_operativo(risultato.config["cap_ev"], "esemplari"))
    tab2.add_row("Filettatura (LFU)", ritmo_operativo(risultato.config["cap_lfu_filetti"], "esemplari"))
    tab2.add_row("Lavorazione uova (LFU)", ritmo_operativo(risultato.config["cap_lfu_uova"], "esemplari"))
    tab2.add_row("Confez. Trota (CF)", ritmo_operativo(risultato.config["cap_cf_trota"], "kg"))
    tab2.add_row("Confez. Filetti (CF)", ritmo_operativo(risultato.config["cap_cf_filetti"], "kg"))
    tab2.add_row("Confez. Uova (CF)", ritmo_operativo(risultato.config["cap_cf_uova"], "vasetti"))
    tab2.add_row("", "")
    tab2.add_row("Resa Eviscerazione", f"{risultato.config['resa_evisc'] * 100:.0f}%")
    tab2.add_row("Resa Filettatura", f"{risultato.config['resa_filetti'] * 100:.0f}%")
    console.print(tab2)

    # 3. Output
    tab3 = Table(title="3. Output finali", box=box.SIMPLE, title_style="bold underline")
    tab3.add_column("Linea", style="bright_green", width=36)
    tab3.add_column("Esemplari", justify="right")
    tab3.add_column("Peso vivo", justify="right")
    tab3.add_column("Resa appl.", justify="right", style="white")
    tab3.add_column("Kg finali", justify="right", style="yellow")
    tab3.add_column("Unità comm.", justify="right")
    for lin in LINEE:
        out_linea = risultato.output_linee[lin]
        if lin == "uova_trota":
            unita = f"{out_linea.vasetti} vasetti (100g)"
            resa_str = f"{risultato.lotto.resa_uova * 100:.2f}%"
        elif lin == "filetti_freschi":
            unita = "kg"
            resa_str = f"{risultato.config['resa_filetti'] * 100:.0f}%"
        else:
            unita = "kg"
            resa_str = f"{risultato.config['resa_evisc'] * 100:.0f}%"

        tab3.add_row(
            out_linea.nome,
            str(out_linea.es),
            f"{out_linea.p_vivo:.2f} kg",
            resa_str,
            f"{out_linea.p_out:.2f} kg",
            unita
        )
    console.print(tab3)

    # 4. Durate fasi
    tab4 = Table(title="4. Durate delle fasi", box=box.SIMPLE, title_style="bold underline")
    tab4.add_column("Linea", style="bright_green", width=36)
    tab4.add_column("Fase", style="white", width=30)
    tab4.add_column("Minuti", justify="right", style="cyan")
    for lin in LINEE:
        prima = True
        for nome, d in risultato.durate[lin].items():
            tab4.add_row(risultato.output_linee[lin].nome if prima else "", nome, f"{d:.2f}")
            prima = False
    console.print(tab4)

    # 5. Cronologia risorse
    console.print(Panel("[bold]5. Cronologia risorse[/]", border_style="blue"))
    for ris in RISORSE:
        fasi = risultato.piani[ris]
        tab5 = Table(title=nome_risorsa(ris), box=box.SIMPLE, title_style="bold")
        tab5.add_column("Linea", style="bright_green", width=18)
        tab5.add_column("Fase", style="white", width=30)
        tab5.add_column("Pronto", justify="right")
        tab5.add_column("Inizio", justify="right")
        tab5.add_column("Fine", justify="right")
        tab5.add_column("Attesa", justify="right")
        for fase in fasi:
            tab5.add_row(
                fase.linea,
                fase.nome,
                f"{fase.ready:.1f}",
                f"{fase.inizio:.1f}",
                f"{fase.fine:.1f}",
                f"{fase.attesa:.1f}"
            )
        console.print(tab5)

    # 6. Tempi per linea
    tab6 = Table(title="6. Tempi per output", box=box.SIMPLE, title_style="bold underline")
    tab6.add_column("Output", style="bright_green", width=36)
    tab6.add_column("Attivo", justify="right")
    tab6.add_column("Att. PS", justify="right")
    tab6.add_column("Att. LFU", justify="right")
    tab6.add_column("Att. CF", justify="right")
    tab6.add_column("Att. TOT", justify="right", style="yellow")
    tab6.add_column("Fine", justify="right", style="cyan")
    for lin in LINEE:
        out_linea = risultato.output_linee[lin]
        tab6.add_row(
            out_linea.nome,
            f"{out_linea.attivo:.2f}",
            f"{out_linea.att_ps:.2f}",
            f"{out_linea.att_lfu:.2f}",
            f"{out_linea.att_cf:.2f}",
            f"{out_linea.att_tot:.2f}",
            f"{out_linea.fine:.2f}  ({formatta_tempo(out_linea.fine)})"
        )
    console.print(tab6)

    # 7. Utilizzo risorse e collo di bottiglia
    tab7 = Table(title="7. Utilizzo risorse", box=box.SIMPLE, title_style="bold underline")
    tab7.add_column("Risorsa", style="gold1", width=34)
    tab7.add_column("Occupata (min)", justify="right")
    tab7.add_column("Util. lotto", justify="right", style="yellow")
    tab7.add_column("Util. turno", justify="right")
    for ris in RISORSE:
        s = risultato.statistiche[ris]
        tab7.add_row(
            nome_risorsa(ris),
            f"{s['occupato']:.2f}",
            f"{s['util_lotto']:.1f}%",
            f"{s['util_turno']:.1f}%"
        )
    console.print(tab7)
    console.print(f"[bold red]Collo di bottiglia principale:[/] {nome_risorsa(risultato.collo_bottiglia)}")

    # 8. Riepilogo
    riep = (
        f"[bold]Tempo totale lotto:[/] {risultato.tempo_totale:.2f} min ({formatta_tempo(risultato.tempo_totale)})\n"
        f"[bold]Turno:[/] {risultato.config['turno_min']} min ({formatta_tempo(risultato.config['turno_min'])})\n"
    )
    if risultato.sforamento > 0:
        riep += f"[bold red]Sforamento turno:[/] {risultato.sforamento:.2f} min"
    else:
        margine = risultato.config['turno_min'] - risultato.tempo_totale
        riep += f"[bold green]Lotto completato entro il turno[/] (margine {margine:.2f} min)"
    console.print(Panel.fit(riep, title="8. Riepilogo", border_style="yellow"))



def scenari():
    """Restituisce tre configurazioni predefinite."""
    base = crea_config()
    picco = crea_config(
        min_es=360,
        max_es=420,
        quota_f_min=0.20,
        quota_f_max=0.22
    )
    lfu_plus = crea_config(
        min_es=360,
        max_es=420,
        quota_f_min=0.20,
        quota_f_max=0.22,
        cap_lfu_filetti=44.0,
        cap_lfu_uova=56.0
    )
    return[("Base", base), ("Picco", picco), ("Picco + LFU", lfu_plus)]


def stampa_confronto(seed=42):
    """Esegue i tre scenari e mostra una tabella comparativa."""
    console.print(Panel("[bold]CONFRONTO SCENARI[/]", border_style="cyan"))
    tab = Table(box=box.SIMPLE)
    tab.add_column("Scenario", style="bright_green", width=20)
    tab.add_column("Tempo lotto", justify="right")
    tab.add_column("Sforo", justify="right")
    tab.add_column("Collo", style="yellow")
    tab.add_column("Util. collo", justify="right")
    for nome, config in scenari():
        r = simula(config, seed, nome)
        s = r.statistiche[r.collo_bottiglia]
        tab.add_row(
            nome,
            f"{r.tempo_totale:.2f} min",
            f"{r.sforamento:.2f} min",
            abbreviazione_risorsa(r.collo_bottiglia),
            f"{s['util_lotto']:.1f}%"
        )
    console.print(tab)



if __name__ == "__main__":
    try:
        seed_input = input("Inserisci seed (premi Invio per 42): ").strip()
        if seed_input == "":
            seed = 42
        else:
            seed = int(seed_input)
    except ValueError:
        console.print("[red]Valore non valido, uso seed=42.[/]")
        seed = 42

    config = crea_config()
    risultato = simula(config, seed=seed, scenario="Scenario base")
    stampa_report(risultato)
    stampa_confronto(seed=seed)
