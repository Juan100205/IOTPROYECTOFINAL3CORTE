// =====================================================================
//  WaterGuard v2.0 - Marco adaptador para OLED 0.96" (SSD1306 128x64)
//
//  La tapa ya impresa trae los postes para la OLED de 2.42" (agujeros
//  68 x 39 mm). Este marco se atornilla en esos mismos 4 postes y
//  sostiene la OLED de 0.96" centrada bajo la ventana de la tapa.
//
//  - El vidrio de la OLED entra en un rebaje por debajo del marco y
//    asoma por una ventana de 25 x 14 mm.
//  - La OLED se fija con 4 tornillos M2 (agujeros alargados porque
//    cada clon trae la separación un poco distinta) o con silicona.
//  - Imprimir en color oscuro (negro): es lo que se ve por la ventana.
//  - Se imprime tal cual (cara grabada sobre la cama), sin soportes.
//
//  Tornillería: 4x M2.5 x 6 (marco -> postes de la tapa)
//               4x M2 x 6 + tuercas, o silicona (OLED -> marco)
// =====================================================================

$fn = 40;

// Marco: mismo tamaño que la PCB de la pantalla grande
marco       = [72, 43.5];
marco_t     = 2.0;
postes_sep  = [68, 39];     // agujeros de los postes de la tapa
postes_d    = 2.9;          // pasante M2.5

// OLED 0.96" (medidas típicas; verificar con la suya)
oled_pcb    = [27.3, 27.8];
oled_holes  = [23.0, 23.5]; // separación típica de agujeros M2
oled_vidrio = [27.0, 19.5]; // vidrio completo
vidrio_t    = 1.4;          // grosor del vidrio (profundidad del rebaje)
vidrio_dy   = 1.0;          // el vidrio va un poco corrido hacia los pines
oled_activa = [25.0, 14.0]; // ventana visible (zona activa ~21.7 x 10.9)
holgura     = 0.3;


module marco_adaptador() {
    difference() {
        translate([-marco[0]/2, -marco[1]/2, 0]) cube([marco[0], marco[1], marco_t]);

        // Agujeros a los postes de la tapa
        for (sx = [-1, 1], sy = [-1, 1])
            translate([sx*postes_sep[0]/2, sy*postes_sep[1]/2, -1])
                cylinder(d = postes_d, h = marco_t + 2);

        // Ventana visible de la pantalla
        translate([0, vidrio_dy, marco_t/2])
            cube([oled_activa[0], oled_activa[1], marco_t + 2], center = true);

        // Rebaje para el vidrio (por la cara de abajo, hacia la PCB)
        translate([0, vidrio_dy, marco_t - vidrio_t/2 + 0.01])
            cube([oled_vidrio[0] + 2*holgura, oled_vidrio[1] + 2*holgura, vidrio_t + 0.02], center = true);

        // Agujeros M2 de la OLED, alargados +-1.5 mm en ambos ejes
        for (sx = [-1, 1], sy = [-1, 1])
            translate([sx*oled_holes[0]/2, sy*oled_holes[1]/2, -1])
                hull() for (d = [[-1.5, 0], [1.5, 0], [0, -1.5], [0, 1.5]])
                    translate([d[0], d[1], 0]) cylinder(d = 2.3, h = marco_t + 2);

    }
}

// Cara visible (la que queda hacia la ventana) es z = 0: va sobre la
// cama; el rebaje del vidrio queda arriba.
marco_adaptador();
