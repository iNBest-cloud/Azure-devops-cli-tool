# Scoring Calculation Examples

Esta guía proporciona ejemplos detallados con datos reales de cómo se calculan las métricas de scoring en el sistema.

## Tabla de Contenidos

1. [Parámetros de Configuración](#parámetros-de-configuración)
2. [Ejemplo 1: Entrega Tardía (3 días)](#ejemplo-1-entrega-tardía-3-días)
3. [Ejemplo 2: Entrega Temprana (5 días)](#ejemplo-2-entrega-temprana-5-días)
4. [Ejemplo 3: Entrega Muy Tardía (15+ días)](#ejemplo-3-entrega-muy-tardía-15-días)
5. [Ejemplo 4: Entrega a Tiempo](#ejemplo-4-entrega-a-tiempo)
6. [Ejemplo 5: Cálculo del Overall Developer Score](#ejemplo-5-cálculo-del-overall-developer-score)
7. [Resumen de Fórmulas](#resumen-de-fórmulas)

---

## Parámetros de Configuración

Para todos los ejemplos, usaremos los valores por defecto del sistema:

```json
{
  "efficiency_scoring": {
    "completion_bonus_percentage": 0.20,
    "max_efficiency_cap": 150.0,
    "early_delivery_thresholds": {
      "very_early_days": 5,
      "early_days": 3,
      "slightly_early_days": 1
    },
    "early_delivery_scores": {
      "very_early": 130.0,
      "early": 120.0,
      "slightly_early": 110.0,
      "on_time": 100.0
    },
    "late_delivery_scores": {
      "late_1_3": 95.0,
      "late_4_7": 90.0,
      "late_8_14": 85.0,
      "late_15_plus": 70.0
    },
    "late_penalty_mitigation": {
      "late_1_3": 2.0,
      "late_4_7": 4.0,
      "late_8_14": 6.0,
      "late_15_plus": 8.0
    }
  },
  "developer_scoring": {
    "weights": {
      "fair_efficiency": 0.2,
      "delivery_score": 0.3,
      "completion_rate": 0.3,
      "on_time_delivery": 0.2
    }
  }
}
```

---

## Ejemplo 1: Entrega Tardía (3 días)

### Datos del Work Item

| Campo | Valor |
|-------|-------|
| **Título** | "Implementar login con OAuth" |
| **Estimated Hours** | 8.0 horas |
| **Active Time** | 6.0 horas |
| **Target Date** | 2025-01-15 |
| **Closed Date** | 2025-01-18 |
| **Estado** | "Closed" (completado) |
| **Días de diferencia** | +3 días (tarde) |

### Paso 1: Calcular Completion Bonus

**Fórmula:**
```
Completion Bonus = Estimated Hours × Completion Bonus Percentage
```

**Cálculo:**
```
Completion Bonus = 8.0 × 0.20 = 1.6 horas
```

✅ **Resultado:** Se agregan 1.6 horas al numerador por estar completado.

---

### Paso 2: Determinar Delivery Timing

Como se entregó **3 días tarde**, corresponde a la categoría `late_1_3`:

| Métrica | Valor | Fuente |
|---------|-------|--------|
| **Delivery Score** | 95.0 | `late_delivery_scores.late_1_3` |
| **Late Penalty Mitigation** | 2.0 horas | `late_penalty_mitigation.late_1_3` |

---

### Paso 3: Calcular Fair Efficiency

**Fórmula:**
```
Fair Efficiency = (Numerador / Denominador) × 100
```

**Numerador:**
```
Numerador = Active Hours + Completion Bonus
Numerador = 6.0 + 1.6 = 7.6 horas
```

**Denominador:**
```
Denominador = Estimated Hours + Late Penalty Mitigation
Denominador = 8.0 + 2.0 = 10.0 horas
```

**Fair Efficiency:**
```
Fair Efficiency = (7.6 / 10.0) × 100 = 76.0%
```

✅ **Resultado:** Fair Efficiency = **76.0%**

---

### Resumen del Work Item

| Métrica | Valor | Explicación |
|---------|-------|-------------|
| Active Hours | 6.0h | Tiempo real trabajado en estados productivos |
| Estimated Hours | 8.0h | Tiempo estimado original |
| Completion Bonus | 1.6h | 20% de 8h (bonus por estar completado) |
| Late Penalty Mitigation | 2.0h | Mitigación por entregar 3 días tarde |
| **Fair Efficiency** | **76.0%** | (7.6 / 10.0) × 100 |
| **Delivery Score** | **95.0** | Puntos por entregar 1-3 días tarde |
| Days Ahead/Behind | +3 días | Diferencia con fecha objetivo |

---

## Ejemplo 2: Entrega Temprana (5 días)

### Datos del Work Item

| Campo | Valor |
|-------|-------|
| **Título** | "Refactorizar módulo de autenticación" |
| **Estimated Hours** | 10.0 horas |
| **Active Time** | 7.0 horas |
| **Target Date** | 2025-01-20 |
| **Closed Date** | 2025-01-15 |
| **Estado** | "Closed" (completado) |
| **Días de diferencia** | -5 días (temprano) |

### Paso 1: Calcular Completion Bonus

```
Completion Bonus = 10.0 × 0.20 = 2.0 horas
```

✅ **Resultado:** +2.0 horas de bonus

---

### Paso 2: Determinar Delivery Timing

Como se entregó **5 días antes**, corresponde a la categoría `very_early` (≥5 días):

| Métrica | Valor | Fuente |
|---------|-------|--------|
| **Delivery Score** | 130.0 | `early_delivery_scores.very_early` |
| **Timing Bonus Hours** | 5.0 horas | 5 días × 1.0 (no se usa en fair efficiency) |
| **Late Penalty Mitigation** | 0.0 horas | No aplica (entrega temprana) |

---

### Paso 3: Calcular Fair Efficiency

**Numerador:**
```
Numerador = Active Hours + Completion Bonus
Numerador = 7.0 + 2.0 = 9.0 horas
```

**Denominador:**
```
Denominador = Estimated Hours + Late Penalty Mitigation
Denominador = 10.0 + 0.0 = 10.0 horas
```

**Fair Efficiency:**
```
Fair Efficiency = (9.0 / 10.0) × 100 = 90.0%
```

✅ **Resultado:** Fair Efficiency = **90.0%**

---

### Resumen del Work Item

| Métrica | Valor | Explicación |
|---------|-------|-------------|
| Active Hours | 7.0h | Tiempo real trabajado |
| Estimated Hours | 10.0h | Tiempo estimado |
| Completion Bonus | 2.0h | 20% de 10h |
| **Fair Efficiency** | **90.0%** | (9.0 / 10.0) × 100 |
| **Delivery Score** | **130.0** | Puntos por entregar 5+ días antes |
| Days Ahead/Behind | -5 días | 5 días antes de la fecha objetivo |

---

## Ejemplo 3: Entrega Muy Tardía (15+ días)

### Datos del Work Item

| Campo | Valor |
|-------|-------|
| **Título** | "Migrar base de datos legacy" |
| **Estimated Hours** | 16.0 horas |
| **Active Time** | 12.0 horas |
| **Target Date** | 2025-01-10 |
| **Closed Date** | 2025-01-30 |
| **Estado** | "Closed" (completado) |
| **Días de diferencia** | +20 días (muy tarde) |

### Paso 1: Calcular Completion Bonus

```
Completion Bonus = 16.0 × 0.20 = 3.2 horas
```

✅ **Resultado:** +3.2 horas de bonus

---

### Paso 2: Determinar Delivery Timing

Como se entregó **20 días tarde**, corresponde a la categoría `late_15_plus` (≥15 días):

| Métrica | Valor | Fuente |
|---------|-------|--------|
| **Delivery Score** | 70.0 | `late_delivery_scores.late_15_plus` |
| **Late Penalty Mitigation** | 8.0 horas | `late_penalty_mitigation.late_15_plus` |

---

### Paso 3: Calcular Fair Efficiency

**Numerador:**
```
Numerador = Active Hours + Completion Bonus
Numerador = 12.0 + 3.2 = 15.2 horas
```

**Denominador:**
```
Denominador = Estimated Hours + Late Penalty Mitigation
Denominador = 16.0 + 8.0 = 24.0 horas
```

**Fair Efficiency:**
```
Fair Efficiency = (15.2 / 24.0) × 100 = 63.3%
```

✅ **Resultado:** Fair Efficiency = **63.3%**

---

### Resumen del Work Item

| Métrica | Valor | Explicación |
|---------|-------|-------------|
| Active Hours | 12.0h | Tiempo real trabajado |
| Estimated Hours | 16.0h | Tiempo estimado |
| Completion Bonus | 3.2h | 20% de 16h |
| Late Penalty Mitigation | 8.0h | Mitigación máxima por 15+ días tarde |
| **Fair Efficiency** | **63.3%** | (15.2 / 24.0) × 100 |
| **Delivery Score** | **70.0** | Puntos por entregar 15+ días tarde |
| Days Ahead/Behind | +20 días | 20 días después de la fecha objetivo |

**Nota:** Aunque el trabajo se completó en menos tiempo del estimado (12h vs 16h), la entrega muy tardía reduce significativamente la eficiencia debido a la mitigación de penalización.

---

## Ejemplo 4: Entrega a Tiempo

### Datos del Work Item

| Campo | Valor |
|-------|-------|
| **Título** | "Agregar validación de formularios" |
| **Estimated Hours** | 4.0 horas |
| **Active Time** | 3.5 horas |
| **Target Date** | 2025-01-25 |
| **Closed Date** | 2025-01-25 |
| **Estado** | "Closed" (completado) |
| **Días de diferencia** | 0 días (a tiempo) |

### Paso 1: Calcular Completion Bonus

```
Completion Bonus = 4.0 × 0.20 = 0.8 horas
```

✅ **Resultado:** +0.8 horas de bonus

---

### Paso 2: Determinar Delivery Timing

Como se entregó **exactamente a tiempo** (0 días de diferencia):

| Métrica | Valor | Fuente |
|---------|-------|--------|
| **Delivery Score** | 100.0 | `early_delivery_scores.on_time` |
| **Late Penalty Mitigation** | 0.0 horas | No aplica (entrega a tiempo) |

---

### Paso 3: Calcular Fair Efficiency

**Numerador:**
```
Numerador = Active Hours + Completion Bonus
Numerador = 3.5 + 0.8 = 4.3 horas
```

**Denominador:**
```
Denominador = Estimated Hours + Late Penalty Mitigation
Denominador = 4.0 + 0.0 = 4.0 horas
```

**Fair Efficiency:**
```
Fair Efficiency = (4.3 / 4.0) × 100 = 107.5%
```

✅ **Resultado:** Fair Efficiency = **107.5%**

---

### Resumen del Work Item

| Métrica | Valor | Explicación |
|---------|-------|-------------|
| Active Hours | 3.5h | Tiempo real trabajado |
| Estimated Hours | 4.0h | Tiempo estimado |
| Completion Bonus | 0.8h | 20% de 4h |
| **Fair Efficiency** | **107.5%** | (4.3 / 4.0) × 100 |
| **Delivery Score** | **100.0** | Puntos por entregar a tiempo |
| Days Ahead/Behind | 0 días | Entregado exactamente en la fecha objetivo |

**Nota:** La eficiencia es >100% porque el completion bonus (0.8h) más el tiempo activo (3.5h) supera las horas estimadas (4.0h).

---

## Ejemplo 5: Cálculo del Overall Developer Score

Este ejemplo muestra cómo se combinan todas las métricas para calcular el **Overall Developer Score** de un desarrollador.

### Datos del Desarrollador (Resumen del Mes)

Supongamos que un desarrollador tiene los siguientes promedios y porcentajes:

| Métrica | Valor | Descripción |
|---------|-------|-------------|
| **Average Fair Efficiency** | 85.0% | Promedio de fair efficiency de todos sus items |
| **Average Delivery Score** | 95.0 | Promedio de delivery scores |
| **Completion Rate** | 80.0% | % de items completados vs asignados |
| **On-Time Delivery** | 60.0% | % de items entregados a tiempo |

### Pesos de Configuración

```json
{
  "weights": {
    "fair_efficiency": 0.2,      // 20%
    "delivery_score": 0.3,        // 30%
    "completion_rate": 0.3,       // 30%
    "on_time_delivery": 0.2       // 20%
  }
}
```

### Cálculo del Overall Developer Score

**Fórmula:**
```
Overall Score = (Fair Efficiency × W1) + 
                (Delivery Score × W2) + 
                (Completion Rate × W3) + 
                (On-Time Delivery × W4)
```

**Cálculo paso a paso:**

1. **Contribución de Fair Efficiency:**
   ```
   = 85.0 × 0.2 = 17.0 puntos
   ```

2. **Contribución de Delivery Score:**
   ```
   = 95.0 × 0.3 = 28.5 puntos
   ```

3. **Contribución de Completion Rate:**
   ```
   = 80.0 × 0.3 = 24.0 puntos
   ```

4. **Contribución de On-Time Delivery:**
   ```
   = 60.0 × 0.2 = 12.0 puntos
   ```

**Overall Developer Score:**
```
Overall Score = 17.0 + 28.5 + 24.0 + 12.0 = 81.5 puntos
```

✅ **Resultado:** Overall Developer Score = **81.5**

---

### Interpretación del Score

| Rango | Interpretación |
|-------|----------------|
| 80-100 | Excelente |
| 65-79 | Bueno |
| 60-64 | Aceptable (mínimo) |
| 45-59 | Necesita mejora |
| <45 | Requiere intervención |

En este ejemplo, **81.5 puntos** indica un desempeño **Excelente**.

---

## Resumen de Fórmulas

### Fair Efficiency

```
Fair Efficiency = (Numerador / Denominador) × 100

Donde:
  Numerador = Active Hours + Completion Bonus
  Denominador = Estimated Hours + Late Penalty Mitigation
  
  Completion Bonus = Estimated Hours × 0.20 (si está completado)
  Late Penalty Mitigation = según días de retraso:
    - 1-3 días: 2.0 horas
    - 4-7 días: 4.0 horas
    - 8-14 días: 6.0 horas
    - 15+ días: 8.0 horas
```

### Delivery Score

Puntos fijos según timing:

| Timing | Score |
|--------|-------|
| 5+ días antes | 130.0 |
| 3-4 días antes | 120.0 |
| 1-2 días antes | 110.0 |
| A tiempo | 100.0 |
| 1-3 días tarde | 95.0 |
| 4-7 días tarde | 90.0 |
| 8-14 días tarde | 85.0 |
| 15+ días tarde | 70.0 |

### Overall Developer Score

```
Overall Score = (Fair Efficiency × W1) + 
                (Delivery Score × W2) + 
                (Completion Rate × W3) + 
                (On-Time Delivery × W4)

Donde W1 + W2 + W3 + W4 = 1.0 (100%)
```

---

## Notas Importantes

1. **Completion Bonus:** Solo se aplica si el work item está en estado "Closed", "Done", o "Resolved".

2. **Late Penalty Mitigation:** Aumenta el denominador para suavizar el impacto de entregas tardías. No es un bonus, sino una forma de hacer el cálculo más justo.

3. **Max Efficiency Cap:** Si el Fair Efficiency excede 150%, se capa a 150%.

4. **Delivery Score vs Fair Efficiency:** El Delivery Score es independiente y se usa en el Overall Developer Score. Los timing bonuses NO se agregan al numerador de Fair Efficiency.

5. **On-Time Delivery:** Se calcula como porcentaje de items entregados a tiempo (0 días o antes) vs total de items con datos.

---

## Referencias

- [SCORING_PARAMETERS.md](SCORING_PARAMETERS.md) - Guía completa de parámetros configurables
- [WORK_ITEM_QUERYING_GUIDE.md](WORK_ITEM_QUERYING_GUIDE.md) - Guía de uso del sistema
- [FLOW_DIAGRAM.md](FLOW_DIAGRAM.md) - Diagrama de flujo del proceso de cálculo
