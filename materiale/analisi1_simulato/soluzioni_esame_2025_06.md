# Soluzioni ufficiali — Appello del 20 giugno 2025
Analisi Matematica 1 — Prof.ssa Elena Rinaldi
(Documento riservato alla docente: non distribuire agli studenti.)

## Esercizio 1 (7 punti)

**(a)** $\displaystyle\lim_{x\to0}\frac{e^{2x}-1}{\sin(3x)}$

Passo 1: Sostituendo $x=0$ si ottiene $\frac{e^0-1}{\sin0}=\frac00$: forma indeterminata.

Passo 2: Si moltiplica e divide per $2x$ e per $3x$: $\frac{e^{2x}-1}{\sin(3x)}=\frac{e^{2x}-1}{2x}\cdot\frac{3x}{\sin(3x)}\cdot\frac{2x}{3x}$.

Passo 3: $\frac{e^{2x}-1}{2x}\to1$ per il limite notevole $\lim_{t\to0}\frac{e^t-1}{t}=1$, con $t=2x\to0$.

Passo 4: $\frac{3x}{\sin(3x)}\to1$ per il limite notevole del seno applicato all'argomento $3x\to0$.

Passo 5: $\frac{2x}{3x}=\frac23$; per l'algebra dei limiti (limite del prodotto) il risultato è $1\cdot1\cdot\frac23=\frac23$.

**(b)** $\displaystyle\lim_{x\to0}\frac{1-\cos(2x)}{x\sin x}$

Passo 6: Sostituendo $x=0$ si ottiene $\frac00$: forma indeterminata.

Passo 7: Si fa comparire $(2x)^2$ al denominatore: $\frac{1-\cos(2x)}{x\sin x}=\frac{1-\cos(2x)}{(2x)^2}\cdot\frac{4x^2}{x\sin x}=\frac{1-\cos(2x)}{(2x)^2}\cdot4\cdot\frac{x}{\sin x}$.

Passo 8: $\frac{1-\cos(2x)}{(2x)^2}\to\frac12$ (limite notevole del coseno con argomento $2x\to0$) e $\frac{x}{\sin x}\to1$.

Passo 9: Per l'algebra dei limiti il risultato è $\frac12\cdot4\cdot1=2$.

**(c)** $\displaystyle\lim_{x\to+\infty}\left(1+\frac2x\right)^x$

Passo 10: Per $x\to+\infty$ la base tende a $1$ e l'esponente a $+\infty$: forma indeterminata $1^\infty$.

Passo 11: Per il limite notevole $\left(1+\frac ax\right)^x\to e^a$ con $a=2$, il risultato è $e^2$.

## Esercizio 2 (8 punti)

**(a)** $f(x)=x\,e^{-x^2}$, retta tangente in $x_0=1$

Passo 1: $f$ è il prodotto di $x$ e $e^{-x^2}$: si usa la regola del prodotto $(uv)'=u'v+uv'$.

Passo 2: Per la regola della catena $D[e^{-x^2}]=e^{-x^2}\cdot(-2x)=-2x\,e^{-x^2}$.

Passo 3: Quindi $f'(x)=e^{-x^2}+x\cdot(-2x\,e^{-x^2})=e^{-x^2}(1-2x^2)$.

Passo 4: Valori in $x_0=1$: $f(1)=e^{-1}=\frac1e$ e $f'(1)=e^{-1}(1-2)=-\frac1e$.

Passo 5: L'equazione della retta tangente in $x_0$ è $y=f(x_0)+f'(x_0)(x-x_0)$.

Passo 6: Sostituendo: $y=\frac1e-\frac1e(x-1)$, cioè $y=\frac{2-x}{e}$.

**(b)** $g(x)=\ln\!\left(\frac{x^2}{\sqrt{x+1}}\right)$, $x>0$

Passo 7: Con le proprietà dei logaritmi ($\ln\frac ab=\ln a-\ln b$, $\ln a^k=k\ln a$), per $x>0$: $g(x)=2\ln x-\frac12\ln(x+1)$.

Passo 8: Per linearità e regola della catena: $g'(x)=\frac2x-\frac12\cdot\frac{1}{x+1}$.

Passo 9: Denominatore comune: $g'(x)=\frac{4(x+1)-x}{2x(x+1)}=\frac{3x+4}{2x(x+1)}$.

## Esercizio 3 (7 punti)

**(a)** $\displaystyle\int x\sqrt{x^2+1}\,dx$

Passo 1: Si osserva che $2x$ è la derivata di $x^2+1$: si pone $t=x^2+1$, quindi $dt=2x\,dx$ e $x\,dx=\frac12dt$.

Passo 2: L'integrale diventa $\frac12\int t^{1/2}\,dt$.

Passo 3: Con la tabella degli integrali immediati: $\frac12\cdot\frac{t^{3/2}}{3/2}=\frac{t^{3/2}}{3}$.

Passo 4: Tornando alla variabile $x$: $\int x\sqrt{x^2+1}\,dx=\frac13(x^2+1)^{3/2}+c=\frac13(x^2+1)\sqrt{x^2+1}+c$.

**(b)** $\displaystyle\int\sin^2x\,dx$

Passo 5: Si usa l'identità $\sin^2x=\frac{1-\cos(2x)}{2}$ (dalla formula di duplicazione $\cos(2x)=1-2\sin^2x$).

Passo 6: Per linearità: $\int\sin^2x\,dx=\frac12\int1\,dx-\frac12\int\cos(2x)\,dx$.

Passo 7: Con l'argomento lineare: $\int\cos(2x)\,dx=\frac12\sin(2x)+c$.

Passo 8: Risultato: $\int\sin^2x\,dx=\frac x2-\frac{\sin(2x)}{4}+c$.

Passo 9: Verifica derivando: $\frac12-\frac{2\cos(2x)}{4}=\frac{1-\cos(2x)}{2}=\sin^2x$.

## Esercizio 4 (8 punti)

**(a)** $\displaystyle\int_0^{\pi/2}\sin x\cos^2x\,dx$

Passo 1: Si pone $t=\cos x$, quindi $dt=-\sin x\,dx$.

Passo 2: Si cambiano gli estremi di integrazione: per $x=0$ si ha $t=\cos0=1$; per $x=\frac\pi2$ si ha $t=\cos\frac\pi2=0$.

Passo 3: L'integrale diventa $\int_1^0t^2\,(-dt)=\int_0^1t^2\,dt$ (scambiando gli estremi cambia il segno).

Passo 4: Per il teorema fondamentale: $\left[\frac{t^3}{3}\right]_0^1=\frac13$.

**(b)** $\displaystyle\int_1^e x\ln x\,dx$

Passo 5: Si integra per parti scegliendo di derivare il logaritmo e integrare il polinomio: $f=\ln x$, $g'=x$.

Passo 6: Quindi $f'=\frac1x$ e $g=\frac{x^2}{2}$.

Passo 7: Formula per parti negli integrali definiti: $\int_1^e x\ln x\,dx=\left[\frac{x^2}{2}\ln x\right]_1^e-\int_1^e\frac{x^2}{2}\cdot\frac1x\,dx$.

Passo 8: $\left[\frac{x^2}{2}\ln x\right]_1^e=\frac{e^2}{2}\cdot1-\frac12\cdot0=\frac{e^2}{2}$.

Passo 9: $\int_1^e\frac x2\,dx=\left[\frac{x^2}{4}\right]_1^e=\frac{e^2-1}{4}$.

Passo 10: Risultato: $\frac{e^2}{2}-\frac{e^2-1}{4}=\frac{2e^2-e^2+1}{4}=\frac{e^2+1}{4}$.

**(c)** Area tra $f(x)=x^2-1$, l'asse $x$, $x=0$ e $x=2$

Passo 11: Zeri di $f$ in $[0,2]$: $x^2-1=0$ per $x=1$; $f<0$ su $[0,1)$ e $f>0$ su $(1,2]$.

Passo 12: Poiché $f$ cambia segno, l'area è $\int_0^2|f(x)|\,dx=\int_0^1(1-x^2)\,dx+\int_1^2(x^2-1)\,dx$.

Passo 13: $\int_0^1(1-x^2)\,dx=\left[x-\frac{x^3}{3}\right]_0^1=1-\frac13=\frac23$.

Passo 14: $\int_1^2(x^2-1)\,dx=\left[\frac{x^3}{3}-x\right]_1^2=\left(\frac83-2\right)-\left(\frac13-1\right)=\frac23+\frac23=\frac43$.

Passo 15: Area $=\frac23+\frac43=2$.
