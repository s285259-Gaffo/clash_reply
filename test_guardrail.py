"""Prove locali dei guardrail; non richiedono chiavi API o chiamate al modello."""
import unittest

import fantasma
import materiale
import personas


class GuardrailTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corso = materiale.carica_corso("analisi1_simulato")

    def test_citazione_letterale_nello_stesso_frammento(self):
        c = self.corso
        self.assertFalse(materiale.verifica_citazione(c, "S6", "")["valida"])
        self.assertTrue(materiale.verifica_citazione(
            c, "S6", "Il limite notevole resta vero se al posto di")["valida"])
        self.assertFalse(materiale.verifica_citazione(
            c, "S6", "Il seno ha sempre limite uguale a uno")["valida"])
        # Una frase del minuto successivo non giustifica il minuto indicato.
        self.assertFalse(materiale.verifica_citazione(
            c, "L2@25:15", "Quindi y uguale nove più sei per x meno tre")["valida"])

    def test_falso_amico_e_citazione_fuori_tema(self):
        c = self.corso
        passo_seno = {"testo": "Limite notevole del seno con argomento 3x"}
        cit_seno = "Se $g(x)\\to0$ per $x\\to x_0$, allora $\\frac{\\sin g(x)}{g(x)}\\to1$"
        self.assertTrue(materiale.verifica_citazione(c, "S6", cit_seno)["valida"])
        self.assertTrue(personas.verifica_pertinenza(passo_seno, c.fonti["S6"], cit_seno)["valida"])
        passo_exp = {"testo": "Limite notevole dell'esponenziale (e^t - 1)/t"}
        cit_estranea = "lim_{x\\to0}\\frac{\\sin x}{x}=1"
        self.assertFalse(personas.verifica_pertinenza(
            passo_exp, c.fonti["S5"], cit_estranea)["valida"])

    def test_esempio_simile_non_basta_etichetta(self):
        c = self.corso
        passo = {"testo": "Integrare per parti derivando il logaritmo"}
        riga_estranea = personas._righe(c.fonti["S26"])[0]
        riga_simile = personas._righe(c.fonti["S27"])[1]
        self.assertFalse(personas.esempio_simile(c, c.fonti["S26"], riga_estranea, passo))
        self.assertTrue(personas.esempio_simile(c, c.fonti["S27"], riga_simile, passo))

    def test_json_incompleto_bloccato(self):
        risposta = {"passi": [{"esercizio": "1", "passo": 1,
                               "stato": "non_trovato"}]}
        with self.assertRaisesRegex(ValueError, "passi mancanti"):
            fantasma.valida_output("fantasma_slide", risposta, {("1", "1"), ("1", "2")})
        with self.assertRaisesRegex(ValueError, "esercizi mancanti"):
            fantasma.valida_output("analista", {
                "corso": "Analisi 1", "obiettivi": ["Calcolare limiti"],
                "esercizi": [{"id": "1", "punti": 7, "passi": [
                    {"n": 1, "testo": "passo", "tipo": "teoria", "minuti_stimati": 1}]}],
                "durata_esame_minuti": 120, "domande_per_il_docente": []}, {"1", "2"})

    def test_classificazione_non_scambia_seno_esponenziale(self):
        c = self.corso
        brief = {"esercizi": [{"id": "1", "punti": 7, "passi": [
            {"n": 3, "tipo": "teoria", "testo": "Limite notevole dell'esponenziale (e^t - 1)/t", "minuti_stimati": 1},
            {"n": 4, "tipo": "teoria", "testo": "Limite notevole del seno con argomento 3x", "minuti_stimati": 1}]}]}
        slide = {"passi": [
            {"esercizio": "1", "passo": 3, "stato": "giustificato", "fonte": "S5",
             "citazione": "\\lim_{x\\to0}\\frac{\\sin x}{x}=1"},
            {"esercizio": "1", "passo": 4, "stato": "giustificato", "fonte": "S6",
             "citazione": "Se $g(x)\\to0$ per $x\\to x_0$, allora $\\frac{\\sin g(x)}{g(x)}\\to1$"}]}
        analisi = fantasma.verifica_e_classifica(c, brief, slide, {"passi": []}, {}, {})
        self.assertEqual([(g["tipo"], g["passo"]) for g in analisi["lacune"]], [("rossa", "3")])


if __name__ == "__main__":
    unittest.main()
