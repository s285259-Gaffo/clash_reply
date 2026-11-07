# Analisi Matematica 1 — Lezione 1: Limiti e limiti notevoli
Prof.ssa Elena Rinaldi — Corso di Laurea in Ingegneria, primo anno

## Slide 1 — Il concetto di limite
- Idea: studiare il comportamento di $f(x)$ quando $x$ si avvicina a $x_0$ (anche se $f$ non è definita in $x_0$)
- Scriviamo $\lim_{x\to x_0} f(x) = \ell$
- Definizione: per ogni $\varepsilon>0$ esiste $\delta>0$ tale che $0<|x-x_0|<\delta \Rightarrow |f(x)-\ell|<\varepsilon$
- Il valore $f(x_0)$ **non conta**: conta solo cosa succede vicino a $x_0$
- Esempio: $f(x)=\frac{x^2-1}{x-1}$ non è definita in $1$, ma $\lim_{x\to1} f(x) = \lim_{x\to1}(x+1) = 2$

## Slide 2 — Limiti all'infinito e limiti infiniti
- $\lim_{x\to+\infty} f(x)=\ell$: asintoto orizzontale $y=\ell$
- $\lim_{x\to x_0} f(x)=\pm\infty$: asintoto verticale $x=x_0$
- Limite destro e sinistro: $\lim_{x\to x_0^+}$, $\lim_{x\to x_0^-}$; il limite esiste se coincidono
- Esempio: $\lim_{x\to0^+}\frac1x=+\infty$, $\lim_{x\to0^-}\frac1x=-\infty$, quindi $\lim_{x\to0}\frac1x$ non esiste

## Slide 3 — Algebra dei limiti
- Se $f\to\ell_1$ e $g\to\ell_2$ (finiti):
  - $f\pm g\to\ell_1\pm\ell_2$, $\quad f\cdot g\to\ell_1\ell_2$, $\quad f/g\to\ell_1/\ell_2$ se $\ell_2\neq0$
- Il limite di un prodotto di più fattori è il prodotto dei limiti (se tutti finiti)
- Funzioni continue: $\lim_{x\to x_0}f(x)=f(x_0)$ (polinomi, $\sin$, $\cos$, $e^x$, $\ln x$ nel loro dominio)
- Esempio: $\lim_{x\to2}(x^3-3x)=8-6=2$

## Slide 4 — Forme indeterminate
- Forme che **non** si risolvono con l'algebra dei limiti: $\frac00,\ \frac{\infty}{\infty},\ 0\cdot\infty,\ \infty-\infty,\ 1^\infty$
- Strategie: scomporre e semplificare, raccogliere il termine dominante, ricondursi a un limite notevole
- Esempio $\frac{\infty}{\infty}$: $\lim_{x\to+\infty}\frac{3x^2+1}{x^2-5}=\lim_{x\to+\infty}\frac{x^2(3+1/x^2)}{x^2(1-5/x^2)}=3$

## Slide 5 — Limiti notevoli (1): funzioni trigonometriche
- $\displaystyle\lim_{x\to0}\frac{\sin x}{x}=1$
- $\displaystyle\lim_{x\to0}\frac{1-\cos x}{x^2}=\frac12$
- Conseguenza: $\lim_{x\to0}\frac{\tan x}{x}=1$ perché $\frac{\tan x}{x}=\frac{\sin x}{x}\cdot\frac{1}{\cos x}\to1\cdot1$
- Interpretazione: vicino a $0$, $\sin x$ "si comporta come" $x$

## Slide 6 — Limiti notevoli con argomento qualsiasi
- **Il limite notevole resta vero se al posto di $x$ c'è una qualunque espressione che tende a zero**
- Se $g(x)\to0$ per $x\to x_0$, allora $\frac{\sin g(x)}{g(x)}\to1$ e $\frac{1-\cos g(x)}{(g(x))^2}\to\frac12$
- Trucco: moltiplicare e dividere per la stessa quantità per far comparire la forma del limite notevole
- Esempio: $\displaystyle\lim_{x\to0}\frac{\sin(5x)}{x}=\lim_{x\to0}\frac{\sin(5x)}{5x}\cdot5=1\cdot5=5$
- Esempio: $\displaystyle\lim_{x\to0}\frac{\sin(4x)}{\sin(2x)}=\lim_{x\to0}\frac{\sin(4x)}{4x}\cdot\frac{2x}{\sin(2x)}\cdot\frac{4x}{2x}=2$

## Slide 7 — Limiti notevoli (2): logaritmo e numero $e$
- $\displaystyle\lim_{x\to0}\frac{\ln(1+x)}{x}=1$
- $\displaystyle\lim_{x\to+\infty}\left(1+\frac1x\right)^x=e\approx2{,}718$ (forma $1^\infty$)
- Generalizzazione: $\displaystyle\lim_{x\to+\infty}\left(1+\frac ax\right)^x=e^a$ per ogni $a\in\mathbb R$
- Esempio: $\displaystyle\lim_{x\to0}\frac{\ln(1+3x)}{x}=\lim_{x\to0}\frac{\ln(1+3x)}{3x}\cdot3=3$
- Esempio: $\displaystyle\lim_{x\to+\infty}\left(1-\frac{1}{x}\right)^x=e^{-1}$

## Slide 8 — Riepilogo ed esercizi
- Prima di tutto: sostituire e capire se c'è una forma indeterminata
- Se c'è $\frac00$ con seni, coseni o logaritmi: cercare il limite notevole giusto
- Esercizi per casa:
  - $\lim_{x\to0}\frac{\sin(7x)}{3x}$ $\quad$ (risultato: $\frac73$)
  - $\lim_{x\to0}\frac{1-\cos(3x)}{x^2}$ $\quad$ (risultato: $\frac92$)
  - $\lim_{x\to+\infty}\left(1+\frac{5}{x}\right)^{x}$ $\quad$ (risultato: $e^5$)
