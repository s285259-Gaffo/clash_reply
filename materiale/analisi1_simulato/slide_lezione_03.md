# Analisi Matematica 1 — Lezione 3: Integrali indefiniti e integrazione per sostituzione
Prof.ssa Elena Rinaldi — Corso di Laurea in Ingegneria, primo anno

## Slide 17 — Primitive
- $F$ è una **primitiva** di $f$ su un intervallo se $F'(x)=f(x)$
- Se $F$ è una primitiva, tutte le primitive sono $F(x)+c$, con $c\in\mathbb R$
- Integrale indefinito: $\int f(x)\,dx=F(x)+c$
- Integrare è l'operazione "inversa" del derivare
- Esempio: $\int 2x\,dx=x^2+c$ perché $D[x^2]=2x$

## Slide 18 — Verifica di un integrale
- Un integrale indefinito si controlla sempre **derivando il risultato**
- Esempio: $\int\cos x\,dx=\sin x+c$: infatti $D[\sin x+c]=\cos x$
- Non dimenticare la costante $+c$

## Slide 19 — Linearità dell'integrale
- $\int(f+g)\,dx=\int f\,dx+\int g\,dx$
- $\int c\,f\,dx=c\int f\,dx$
- Esempio: $\int(6x^2-4x+1)\,dx=2x^3-2x^2+x+c$
- Attenzione: **non** esiste una regola semplice per l'integrale di un prodotto

## Slide 20 — Integrali immediati
| $f(x)$ | $\int f(x)\,dx$ |
|---|---|
| $x^n$ ($n\neq-1$) | $\frac{x^{n+1}}{n+1}+c$ |
| $\frac1x$ | $\ln|x|+c$ |
| $e^x$ | $e^x+c$ |
| $\sin x$ | $-\cos x+c$ |
| $\cos x$ | $\sin x+c$ |
| $\frac{1}{\cos^2x}$ | $\tan x+c$ |
| $\frac{1}{1+x^2}$ | $\arctan x+c$ |
| $\ln x$ | $x\ln x-x+c$ |

## Slide 21 — Funzioni con argomento lineare
- Se $\int f(x)\,dx=F(x)+c$, allora $\int f(ax+b)\,dx=\frac1a F(ax+b)+c$ (con $a\neq0$)
- Esempio: $\int\cos(2x)\,dx=\frac12\sin(2x)+c$
- Esempio: $\int e^{3x+1}\,dx=\frac13e^{3x+1}+c$
- Esempio: $\int(2x-1)^5\,dx=\frac{(2x-1)^6}{12}+c$

## Slide 22 — Integrazione per sostituzione
- Idea: è la regola della catena "letta al contrario"
- Si pone $t=g(x)$, quindi $dt=g'(x)\,dx$
- $\int f(g(x))\,g'(x)\,dx=\int f(t)\,dt=F(t)+c=F(g(x))+c$
- Procedura:
  1. scegliere $t=g(x)$ (di solito l'"interno" la cui derivata compare come fattore)
  2. calcolare $dt$ e riscrivere **tutto** in funzione di $t$
  3. integrare in $t$
  4. tornare alla variabile $x$

## Slide 23 — Sostituzione: esempi svolti
- $\int 2x\cos(x^2)\,dx$: $t=x^2$, $dt=2x\,dx$ $\Rightarrow\int\cos t\,dt=\sin t+c=\sin(x^2)+c$
- $\int\frac{\ln x}{x}\,dx$: $t=\ln x$, $dt=\frac1x dx$ $\Rightarrow\int t\,dt=\frac{t^2}{2}+c=\frac{(\ln x)^2}{2}+c$
- $\int x\,e^{x^2}\,dx$: $t=x^2$, $dt=2x\,dx$, cioè $x\,dx=\frac12dt$ $\Rightarrow\frac12\int e^t dt=\frac12e^{x^2}+c$
- $\int\sin x\cos^3 x\,dx$: $t=\cos x$, $dt=-\sin x\,dx$ $\Rightarrow-\int t^3dt=-\frac{\cos^4x}{4}+c$

## Slide 24 — Due forme da riconoscere
- $\int\frac{f'(x)}{f(x)}\,dx=\ln|f(x)|+c$
  - Esempio: $\int\frac{2x}{x^2+4}\,dx=\ln(x^2+4)+c$
- $\int f'(x)\,(f(x))^n\,dx=\frac{(f(x))^{n+1}}{n+1}+c$ ($n\neq-1$)
  - Esempio: $\int 3x^2(x^3+1)^4\,dx=\frac{(x^3+1)^5}{5}+c$
- Sono casi particolari della sostituzione $t=f(x)$
