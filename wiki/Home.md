# 💧 WaterGuard v8: Wiki del Challenge #2

**Universidad de La Sabana**, Facultad de Ingeniería · Internet de las Cosas 2026-2
**Integrantes:** Juan José Riaño Zabaleta · Santiago Peña Beltrán

Prototipo IoT de bajo costo basado en ESP32 que monitorea la disponibilidad de agua en puntos críticos de almacenamiento de Sabana Centro. Fusiona nivel redundante (ultrasonido + presión hidrostática) con variables meteorológicas para calcular un **índice de evaporación potencial** (Dalton/DPV) y un **Índice de Riesgo Hídrico (IRH)**. Alerta **in situ** y en un **tablero web embebido** restringido a la WLAN de la Alcaldía, sin MQTT.

> *Abstract.* WaterGuard v8 is a low-cost ESP32 IoT prototype that fuses redundant water-level sensing (ultrasonic + hydrostatic) with weather variables to compute a Dalton-based potential-evaporation index and a Water Risk Index. It raises on-site alarms and serves a WLAN-restricted embedded web dashboard (no MQTT), with sensing done in ISRs and FreeRTOS tasks.

## Contenido

1. [Resumen general](1.-Resumen-General): motivación, justificación y estructura
2. [Solución propuesta](2.-Solución-Propuesta)
   - [2.1 Restricciones de diseño](2.1.-Restricciones-de-Diseño)
   - [2.2 Arquitectura propuesta](2.2.-Arquitectura-Propuesta)
   - [2.3 Desarrollo teórico modular (fórmulas e indicadores)](2.3.-Desarrollo-Teórico-Modular)
   - [2.4 Diagramas UML](2.4.-Diagramas-UML)
   - [2.5 Esquemático de hardware](2.5.-Esquemático-de-Hardware)
   - [2.6 Estándares de ingeniería](2.6.-Estándares-de-Ingeniería)
   - [2.7 Modelo de negocio](2.7.-Modelo-de-Negocio)
3. [Configuración experimental, resultados y análisis](3.-Configuración-Experimental,-Resultados-y-Análisis)
4. [Autoevaluación del protocolo de pruebas](4.-Autoevaluación-del-Protocolo-de-Pruebas)
5. [Conclusiones, retos, trabajo futuro](5.-Conclusiones,-Retos-del-Desarrollo,-Trabajo-Futuro-y-Referencias)
6. [Anexos](6.-Anexos)
7. [Roles y contribuciones](7.-Roles-y-Contribuciones)
8. [Video demostrativo](8.-Video-Demostrativo)
9. [Uso de herramientas de IA](9.-Uso-de-Herramientas-de-Inteligencia-Artificial)
10. [Referencias (IEEE)](Referencias)

Repositorio (tercer corte): [Juan100205/IOTPROYECTOFINAL3CORTE](https://github.com/Juan100205/IOTPROYECTOFINAL3CORTE) · Segundo corte: [LeMarsito02/IOTPROYECTOFINAL2CORTE](https://github.com/LeMarsito02/IOTPROYECTOFINAL2CORTE/wiki) · Primer corte: [wiki del Challenge #1](https://github.com/LeMarsito02/IOTPROYECTOFINAL1CORTE/wiki)
