# QuantSignal AI (QuantSignal-Analyzer)

Análisis cuantitativo para cripto, acciones y ETFs (señales multifactor, estructura, Fibonacci, backtesting) con una **bitácora de operaciones trazable** para entrenar la IA con **tus propias decisiones**, no solo con datos pasados del mercado.

## Instalación (una vez)

En la terminal de VS Code, dentro de la carpeta del proyecto:

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

## Uso

| Qué | Comando |
|---|---|
| Menú profesional de consola | `python main.py` |
| Análisis completo de un activo + reporte | `python main.py analyze BTC-USD` |
| Escáner de los 50 activos | `python main.py scan` (añade `--backtest` para incluir las 6 estrategias) |
| Estudio multi-activo (6 estrategias × 50 activos) | `python main.py study` |
| Descargar/actualizar datos del universo | `python main.py data` |
| Backtesting profesional | `python main.py backtest ETH-USD` |
| Actualizar señales y paper trading | `python main.py update` |
| Reporte de la bitácora | `python main.py report` |
| App gráfica | `python main.py app` o `streamlit run app.py` |
| Pruebas | `pytest -q` |

En VS Code: renombra la carpeta `vscode-config` a `.vscode` y tendrás los tres en **Run and Debug** (Ctrl+Shift+D).

## Universo de estudio: 50 activos (v2.2)

| Clase | Activos |
|---|---|
| Cripto (10) | BTC, ETH, SOL, BNB, XRP, ADA, DOGE, AVAX, LINK, DOT |
| Índices y ETF (10) | SPY, QQQ, DIA, IWM, EFA, EEM, TLT, HYG, XLF, XLE |
| Acciones EE.UU. (18) | AAPL, MSFT, NVDA, AMZN, GOOGL, META, TSLA, AMD, AVGO, NFLX, JPM, V, MA, UNH, XOM, LLY, COST, WMT |
| Forex (6) | EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CAD, USD/COP |
| Materias primas (6) | Oro, plata, petróleo WTI, gas natural, cobre, maíz |

Cómo se aprovechan los 50:
- **Análogos entre activos:** para cada análisis se buscan los 100 casos más parecidos en *todo* el universo (máximo 25 por activo), con las variables normalizadas por volatilidad para que sean comparables. Los casos de la misma semana se cuentan una sola vez ("semanas independientes").
- **Estudio multi-activo:** las 6 estrategias sobre los 50 activos (≈ 8.000 operaciones simuladas), con consistencia entre activos, resultados por clase y por año. Todas las operaciones se guardan en `outputs/datasets/estudio_universo_*.csv`.
- **IA:** el dataset de mercado pasa de ~2.300 a ~22.000 muestras.
- **Caché local** en `storage/cache/`: los 50 activos se descargan en lote y se reutilizan durante 6 horas (configurable).

Edita el universo en `config/settings.py` (`UNIVERSE`).

## Qué hace cada análisis (v2.1)

1. **Señal técnica** (EMA, RSI, MACD, ADX, estructura, Fibonacci) con **confluencia direccional**: LONG y SHORT se puntúan por separado.
2. **Escenarios del presente**: busca las 60 situaciones históricas más parecidas (análogos) y las compara con un Monte Carlo aleatorio con la volatilidad actual. Da la probabilidad de tocar TP1/TP2/TP3 antes que el stop, la **ventaja sobre el azar**, el valor esperado neto de costes y Kelly.
3. **Backtesting profesional**: 6 estrategias sobre los mismos datos (entrada a la apertura siguiente, comisiones y slippage), con IC95, p-valor, Probabilistic/Deflated Sharpe, SQN, CAGR, Sharpe, Sortino, Calmar, Ulcer, Monte Carlo, riesgo de ruina, estabilidad walk-forward, regímenes y mapa de sensibilidad de parámetros.
4. **Recomendación** que une todo, con **Decision Score** 0-100, riesgo sugerido y sus razones.
5. **Reporte HTML** profesional (se abre solo, funciona sin internet, modo claro/oscuro, móvil).

Ajusta capital, riesgo, watchlist, costes y temporalidad desde **Configuración** (menú 8); se guarda en `config/user_settings.json`.

## Flujo recomendado

1. **Analizar** un activo → la señal se guarda con su snapshot completo (indicadores, estructura, features, versión del motor, huella de los datos).
2. **Registrar operación** (manual o a partir de la señal). Anota setup, tesis, confianza y emoción: es lo que la IA aprende de ti.
3. **Gestionar**: mover stop, parciales, notas. Todo queda en la línea de tiempo.
4. **Cerrar** con revisión: ¿seguiste el plan?, errores, lección.
5. **Enriquecer**: el sistema calcula, en la vela de tu entrada, las MISMAS features que usa para sus señales, más MAE/MFE (cuánto fue en contra y a favor).
6. **Evaluar señales**: mide qué habría pasado con cada señal aunque no la operaras.
7. **IA → Construir dataset y entrenar**: combina mercado + señales + tus operaciones (tus operaciones pesan 4×).

## Trazabilidad

La bitácora vive en `storage/quantsignal.db` (SQLite):

- `signals`: cada análisis, con su resultado posterior (WIN/LOSS/TIMEOUT, R, MAE/MFE).
- `trades`: cada operación (MANUAL, PAPER, LIVE, IMPORT), vinculable a la señal que la originó.
- `trade_events`: historial **inmutable** (la base bloquea UPDATE/DELETE) y **encadenado con SHA-256**. Si alguien altera un registro, *Verificar integridad* señala exactamente cuál.
- Las fechas se escriben en hora local (`LOCAL_TZ` en `config/settings.py`) y se guardan en UTC.
- Importación de CSV de tu broker con deduplicación por `broker_ref`.

**Haz copia de seguridad de `storage/`**: son tus datos de entrenamiento.

## Estructura nueva

```
core/analyzer.py        pipeline de análisis que devuelve un dict (sin prints)
journal/                bitácora: db, repositorio, enriquecimiento, menú consola
ml/features.py          features sin sesgo de futuro (mismo esquema para todo)
ml/labeling.py          resultado de un plan: WIN/LOSS/TIMEOUT, R, MAE/MFE
ml/dataset.py           dataset mercado + señales + operaciones
ml/model.py             modelo base P(ganar), validación temporal, historial
reports/performance.py  métricas sobre operaciones reales
reports/html_report.py  reporte HTML autocontenido
app.py                  interfaz Streamlit
tests/                  pruebas (datos sintéticos, sin internet)
outputs/                reportes, gráficas, datasets (generado)
```

## Correcciones v2.1

- La vela del día en curso ya no se analiza (las señales cambiaban durante el día).
- CHOCH era idéntico a BOS: ahora es una ruptura en contra de la estructura vigente.
- La confluencia solo sumaba factores alcistas: un SHORT siempre salía "BAJA".
- El modelo IA ahora se calibra, se compara con una regresión logística, usa embargo temporal y detecta deriva (PSI).

## Correcciones importantes (v2.0)

- 46 archivos tenían **marcadores de conflicto de git** (`<<<<<<< HEAD`) y no se podían ejecutar. Resueltos.
- `calculate_position_size` no devolvía nada.
- Señales `LONG FUERTE` recibían un plan **SHORT** (se comparaba `signal == "LONG"`).
- Backtests: el PnL de operaciones cerradas por tiempo sumaba la diferencia de precio de 1 unidad en vez de escalarla al riesgo. En BTC eso inflaba el retorno y el profit factor (el 545% y el PF 2.93 de los reportes anteriores no son fiables). Además, Fibonacci en el backtest v2 usaba swings futuros.
- El dashboard dibujaba una línea recta interpolada; ahora usa la curva de equity real.
