# Analisi Matematica 1 — Lezione 4: Integrazione per parti e integrali definiti
Prof.ssa Elena Rinaldi — Corso di Laurea in Ingegneria, primo anno

## Slide 25 — Integrazione per parti
- Dalla regola del prodotto: $(fg)'=f'g+fg'$
- Integrando: $\int f(x)\,g'(x)\,dx=f(x)\,g(x)-\int f'(x)\,g(x)\,dx$
- $f$ = fattore che si **deriva**, $g'$ = fattore che si **integra**
- Utile quando $\int f'g$ è più semplice dell'integrale di partenza

## Slide 26 — Per parti: esempi svolti
- $\int x\,e^x\,dx$: $f=x$, $g'=e^x$ $\Rightarrow x\,e^x-\int e^x\,dx=x\,e^x-e^x+c$
- $\int x\cos x\,dx$: $f=x$, $g'=\cos x$ $\Rightarrow x\sin x-\int\sin x\,dx=x\sin x+\cos x+c$
- Verifica: $D[x\sin x+\cos x]=\sin x+x\cos x-\sin x=x\cos x$

## Slide 27 — Per parti: il caso $\int\ln x\,dx$
- Si scrive $\ln x=1\cdot\ln x$: $f=\ln x$, $g'=1$, quindi $f'=\frac1x$, $g=x$
- $\int\ln x\,dx=x\ln x-\int x\cdot\frac1x\,dx=x\ln x-\int1\,dx=x\ln x-x+c$
- Ecco da dove viene la formula della tabella degli integrali immediati

## Slide 28 — Integrale definito
- $f$ continua su $[a,b]$: si divide $[a,b]$ in $n$ parti e si sommano le aree dei rettangoli $f(\xi_i)\,\Delta x$
- Per $n\to\infty$ le somme tendono a un numero: $\int_a^b f(x)\,dx$
- Se $f\ge0$ su $[a,b]$: $\int_a^b f(x)\,dx$ è l'**area** della regione tra il grafico di $f$, l'asse $x$ e le rette $x=a$, $x=b$
- L'integrale definito è un **numero**, non una funzione

## Slide 29 — Proprietà dell'integrale definito
- Linearità: $\int_a^b(\alpha f+\beta g)=\alpha\int_a^b f+\beta\int_a^b g$
- Additività: $\int_a^b f=\int_a^c f+\int_c^b f$
- $\int_b^a f=-\int_a^b f$, $\quad\int_a^a f=0$
- Se $f\le g$ su $[a,b]$ allora $\int_a^b f\le\int_a^b g$

## Slide 30 — Teorema fondamentale del calcolo integrale
- Se $f$ è continua su $[a,b]$, la funzione integrale $F(x)=\int_a^x f(t)\,dt$ è derivabile e $F'(x)=f(x)$
- Conseguenza (formula di Newton–Leibniz): se $G$ è una qualsiasi primitiva di $f$,
  $\int_a^b f(x)\,dx=G(b)-G(a)=\big[G(x)\big]_a^b$
- Per calcolare un integrale definito: **trovare una primitiva e valutarla agli estremi**

## Slide 31 — Integrali definiti: esempi
- $\int_0^3x^2\,dx=\left[\frac{x^3}{3}\right]_0^3=9-0=9$ (area sotto la parabola tra $0$ e $3$)
- $\int_0^\pi\sin x\,dx=[-\cos x]_0^\pi=1-(-1)=2$
- $\int_1^e\frac1x\,dx=[\ln x]_1^e=1-0=1$

## Slide 32 — Per parti negli integrali definiti
- $\int_a^b f(x)\,g'(x)\,dx=\big[f(x)\,g(x)\big]_a^b-\int_a^b f'(x)\,g(x)\,dx$
- Esempio: $\int_0^1x\,e^x\,dx=\big[x\,e^x\big]_0^1-\int_0^1e^x\,dx=e-(e-1)=1$
- Il termine $[fg]_a^b$ va valutato subito agli estremi
