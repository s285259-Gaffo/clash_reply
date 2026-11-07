# Analisi Matematica 1 — Lezione 2: Derivate e regole di derivazione
Prof.ssa Elena Rinaldi — Corso di Laurea in Ingegneria, primo anno

## Slide 9 — Rapporto incrementale e derivata
- Rapporto incrementale di $f$ in $x_0$: $\frac{f(x_0+h)-f(x_0)}{h}$
- Derivata: $f'(x_0)=\lim_{h\to0}\frac{f(x_0+h)-f(x_0)}{h}$ (se il limite esiste finito)
- Altre notazioni: $\frac{df}{dx}$, $Df(x)$
- Esempio: $f(x)=x^2$: $\frac{(x_0+h)^2-x_0^2}{h}=2x_0+h\to2x_0$, quindi $f'(x_0)=2x_0$

## Slide 10 — Significato geometrico
- Il rapporto incrementale è la pendenza della retta secante per $(x_0,f(x_0))$ e $(x_0+h,f(x_0+h))$
- Per $h\to0$ la secante tende alla **retta tangente**
- $f'(x_0)$ = **coefficiente angolare** della retta tangente al grafico in $x_0$
- $f'(x_0)>0$: $f$ crescente vicino a $x_0$; $\ f'(x_0)<0$: decrescente
- Derivabile $\Rightarrow$ continua (il viceversa è falso: $|x|$ in $0$)

## Slide 11 — Derivate delle funzioni elementari
| $f(x)$ | $f'(x)$ |
|---|---|
| $c$ (costante) | $0$ |
| $x^n$ | $n\,x^{n-1}$ (vale per ogni esponente reale) |
| $\sqrt x$ | $\frac{1}{2\sqrt x}$ |
| $e^x$ | $e^x$ |
| $\ln x$ | $\frac1x$ |
| $\sin x$ | $\cos x$ |
| $\cos x$ | $-\sin x$ |
| $\tan x$ | $\frac{1}{\cos^2x}$ |

## Slide 12 — Linearità
- $(f+g)'=f'+g'$
- $(c\,f)'=c\,f'$ per ogni costante $c$
- Esempio: $D[3x^4-2\sqrt x+5]=12x^3-\frac{1}{\sqrt x}$
- Esempio: $D[2\ln x-\cos x]=\frac2x+\sin x$

## Slide 13 — Regola del prodotto
- $(f\cdot g)'=f'\,g+f\,g'$
- Attenzione: $(fg)'\neq f'g'$
- Esempio: $D[x^2\sin x]=2x\sin x+x^2\cos x$
- Esempio: $D[x\,e^x]=e^x+x\,e^x=e^x(1+x)$

## Slide 14 — Regola del quoziente
- $\left(\frac fg\right)'=\frac{f'\,g-f\,g'}{g^2}$ (dove $g\neq0$)
- Esempio: $D\left[\frac{x}{x^2+1}\right]=\frac{1\cdot(x^2+1)-x\cdot2x}{(x^2+1)^2}=\frac{1-x^2}{(x^2+1)^2}$
- Esempio: si ritrova $D[\tan x]=D\left[\frac{\sin x}{\cos x}\right]=\frac{\cos^2x+\sin^2x}{\cos^2x}=\frac{1}{\cos^2x}$

## Slide 15 — Regola della catena (funzione composta)
- Se $h(x)=f(g(x))$, allora $h'(x)=f'(g(x))\cdot g'(x)$
- "Derivata della funzione esterna calcolata nella interna, per la derivata della interna"
- Esempio: $D[\sin(3x)]=3\cos(3x)$
- Esempio: $D[e^{x^2}]=2x\,e^{x^2}$
- Esempio: $D[\ln(x^2+1)]=\frac{2x}{x^2+1}$
- Esempio: $D[\sqrt{1+x^2}]=\frac{2x}{2\sqrt{1+x^2}}=\frac{x}{\sqrt{1+x^2}}$

## Slide 16 — Regole combinate
- Spesso servono più regole insieme: prodotto + catena, quoziente + catena
- Esempio: $D[x\,e^{-x}]=e^{-x}+x\cdot(-e^{-x})=e^{-x}(1-x)$
- Esempio: $D[x^2\cos(2x)]=2x\cos(2x)-2x^2\sin(2x)$
- Punti stazionari: soluzioni di $f'(x)=0$
- Esempio: $f(x)=x\,e^{-x}$ ha $f'(x)=0$ solo per $x=1$
