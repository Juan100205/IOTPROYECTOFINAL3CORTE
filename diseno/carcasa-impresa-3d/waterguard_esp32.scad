// =====================================================================
//  WaterGuard v2.0 - Nodo de sensores con ESP32 (la Raspberry es el gateway)
//  Base + tapa imprimibles sin soportes. Paramétrico.
//
//  Vista desde arriba (frente = abajo):
//
//    +-----------------------------+---+----------------+
//    |  2x 18650 (portapilas)      | a |  CÁMARA DE     |
//    |  [pantalla OLED encima]     | i |  SENSORES      |
//    |-----------------------------| r |  DHT11, BMP280 |
//    |  BAQUELA 5x7:  ESP32        | e |  HC-SR04 (piso)|
//    |  TP4056 + elevador 5V       |   |  [panel solar] |
//    +-----------------------------+---+----------------+
//       LEDs R A V   marca   interruptor
//
//  Exportar:  part = "base" | "tapa" | "conjunto" | "impresion"
// =====================================================================

part = "conjunto"; // [conjunto, base, tapa, impresion]
marca = "WaterGuard v2.0";

/* ---------- Generales ---------- */
t      = 2.4;   // pared
piso   = 2.0;   // piso
tol    = 0.3;   // tolerancia de encaje de la tapa
tapa_t = 2.4;   // grosor de la tapa
$fn    = 40;

/* ---------- Compartimento de electrónica ---------- */
e_x     = 84;   // ancho interior
in_y    = 98;   // fondo interior (común a los dos compartimentos)
alto_in = 36;   // alto interior

/* ---------- Baquela 5x7 cm con el ESP32 ---------- */
baq       = [70, 50];  // baquela de 5 x 7 cm (70 a lo ancho)
baq_borde = 2.5;       // agujeros de las esquinas
baq_h     = 6;         // postes: espacio para las soldaduras por debajo
// ESP32 DevKit (30 pines ~52x28, 38 pines ~55x28). Va en pines hembra
// con el USB hacia la pared izquierda.
esp       = [55, 28];
header_h  = 8.5;       // altura de los pines hembra
usb_win   = [14, 10];  // ventana del USB (cabe el enchufe del cable)

/* ---------- Pilas ---------- */
bat = [77, 41, 21];    // portapilas doble 18650

/* ---------- Cámara de sensores ---------- */
gap_aire = 3;          // cámara de aire entre compartimentos
sens_x   = 52;         // ancho interior (cabe el panel de 50x50 encima)
ped_h    = 14;
dht_ped  = [28, 14];
bmp_ped  = [16, 13];

/* ---------- HC-SR04 (mirando hacia abajo) ---------- */
sr_holes = [42, 17];
sr_sep   = 26;
sr_d     = 16.8;
sr_alto  = 12;

/* ---------- OLED 2.42" ---------- */
disp_pcb     = [72, 43.5];
disp_holes   = [68, 39];
disp_ventana = [57, 29.5];
disp_off     = [0, 0];
disp_alto    = 2.5;

/* ---------- Panel, LDR, LEDs, interruptor, DS18B20 ---------- */
panel        = [50, 50];
panel_rebaje = 1.2;
ldr_d   = 5.2;
led_d   = 5.1;
led_sep = 8;
led_txt = ["R", "A", "V"];
int_d   = 12;
ds_cable_d = 5;

/* ---------- Derivados ---------- */
x_div1 = t + e_x;                    // primera pared del separador
x_sens = x_div1 + 2*t + gap_aire;    // inicio interior cámara de sensores
out_x  = x_sens + sens_x + t;
out_y  = in_y + 2*t;
out_z  = piso + alto_in;

baq_x0 = t + 2;           baq_y0 = t + 1;
esp_x0 = baq_x0;          esp_y0 = baq_y0 + baq[1] - esp[1] - 1;
esp_z0 = piso + baq_h + 1.6 + header_h;          // cara inferior del ESP32
bat_x0 = t + (e_x - bat[0]) / 2;  bat_y0 = t + in_y - bat[1] - 2;

scx = x_sens + sens_x/2;  scy = t + in_y/2;      // centro cámara sensores
dcx = t + e_x/2;          dcy = t + 74;          // centro de la pantalla
ds_x = t + 78;            ds_y = t + 10;         // cable DS18B20 (piso)

oreja_d = 9; tor_d = 2.6; tor_lib = 3.4;
labio_h = 3;
x_gap = x_div1 + t + gap_aire/2;
function esquinas() = [[0,0],[out_x,0],[0,out_y],[out_x,out_y],[x_gap,0],[x_gap,out_y]];

/* =========================== BASE =========================== */
module caja_exterior(h) {
    cube([out_x, out_y, h]);
    for (p = esquinas()) translate([p[0], p[1], 0]) cylinder(d = oreja_d, h = h);
}

module base() {
    difference() {
        caja_exterior(out_z);
        translate([t, t, piso])              cube([e_x, in_y, alto_in + 1]);
        translate([x_div1 + t, t, piso])     cube([gap_aire, in_y, alto_in + 1]);
        translate([x_sens, t, piso])         cube([sens_x, in_y, alto_in + 1]);

        // Tornillos: tapa por arriba, soporte del tanque por abajo
        for (p = esquinas()) translate([p[0], p[1], -1]) cylinder(d = tor_d, h = out_z + 2);

        usb_esp32();
        leds();
        interruptor();
        ventilacion();
        persianas_sensores();
        rejilla_piso_sensores();
        paso_cables_hueco();
        hcsr04_agujeros();
        translate([ds_x, ds_y, -1]) cylinder(d = ds_cable_d, h = piso + 2);   // DS18B20
    }
    postes_baquela();
    topes_pilas();
    viseras();
    paso_cables_tubo();
    hcsr04_postes();
    pedestales();
}

/* ---------- USB del ESP32 (pared izquierda) ---------- */
usb_y = esp_y0 + esp[1]/2;  usb_z = esp_z0 + 1.6 + 1.5;
module usb_esp32() {
    translate([-1, usb_y - usb_win[0]/2, usb_z - usb_win[1]/2]) cube([t + 2, usb_win[0], usb_win[1]]);
}

/* ---------- LEDs, interruptor, marca (frente) ---------- */
led_z = piso + 22;
module leds() {
    for (i = [0:2]) {
        x = t + 10 + i*led_sep;
        translate([x, -1, led_z]) rotate([-90, 0, 0]) cylinder(d = led_d, h = t + 2);
        translate([x, 0.6, led_z - 8]) rotate([90, 0, 0]) linear_extrude(1)
            text(led_txt[i], size = 4, halign = "center", valign = "center", font = "Liberation Sans:style=Bold");
    }
}
module interruptor() {
    translate([t + 70, -1, piso + 24]) rotate([-90, 0, 0]) cylinder(d = int_d, h = t + 2);
}
module marca_frente() {
    translate([t + e_x/2, 0.8, piso + 7]) rotate([90, 0, 0]) linear_extrude(1)
        text(marca, size = 7, halign = "center", valign = "center", font = "Liberation Sans:style=Bold");
}

/* ---------- Persianas a 45° (no entra la lluvia) ---------- */
paso_p = 4.5; alto_p = 2.0;
module ranuras_persiana(largo, z_ini = piso + 4, z_fin = out_z - 6) {
    for (z0 = [z_ini : paso_p : z_fin])
        hull() {
            translate([0, -0.5, z0])            cube([largo, 0.01, alto_p]);
            translate([0, t + 0.5, z0 + t + 1]) cube([largo, 0.01, alto_p]);
        }
}
// Electrónica: unas pocas ranuras para que no se condense humedad adentro
module ventilacion() {
    translate([0, t + 92, 0]) rotate([0, 0, -90]) ranuras_persiana(36, piso + 22);
}
module persianas_sensores() {
    translate([out_x, t + 6, 0]) rotate([0, 0, 90]) ranuras_persiana(in_y - 12);       // derecha
    translate([x_sens + 4, 0, 0]) ranuras_persiana(sens_x - 8);                         // frente
    translate([x_sens + sens_x - 4, out_y, 0]) rotate([0, 0, 180]) ranuras_persiana(sens_x - 8);  // atrás
}
module rejilla_piso_sensores() {
    for (x = [x_sens + 3, x_sens + sens_x - 7], y = [t + 6 : 5 : t + in_y - 8])
        if (abs(y + 1.1 - scy) > 13) translate([x, y, -1]) cube([4, 2.2, piso + 2]);
}

/* ---------- Viseras (cara inferior a 45°, imprimen sin soportes) ---------- */
visera = 5;
module visera_prisma(largo) {
    rotate([90, 0, 90]) linear_extrude(largo) polygon([[0, 0], [visera, visera], [0, visera]]);
}
module viseras() {
    // Sobre el USB del ESP32
    translate([0, usb_y - usb_win[0]/2 - 3, usb_z + usb_win[1]/2 + 0.5]) rotate([0, 0, 90]) visera_prisma(usb_win[0] + 6);
}

/* ---------- Postes de la baquela y topes del portapilas ---------- */
module postes_baquela() {
    for (x = [baq_borde, baq[0] - baq_borde], y = [baq_borde, baq[1] - baq_borde])
        translate([baq_x0 + x, baq_y0 + y, piso - 0.01])
            difference() {
                union() { cylinder(d = 5, h = baq_h); cylinder(d1 = 7, d2 = 5, h = 2); }
                cylinder(d = 1.8, h = baq_h + 1);   // M2 autorroscante
            }
}
module topes_pilas() {   // 4 escuadras bajas que ubican el portapilas (se fija con cinta doble faz)
    for (sx = [0, 1], sy = [0, 1])
        translate([bat_x0 + sx*bat[0] - (sx ? 0 : 3) + (sx ? 0.5 : -0.5),
                   bat_y0 + sy*bat[1] - (sy ? 0 : 3) + (sy ? 0.5 : -0.5), piso - 0.01])
            cube([3, 3, 5]);
}

/* ---------- Paso de cables electrónica <-> sensores ---------- */
pc_y = t + 30; pc_z = piso + 22; pc_d = 10;
module paso_cables_hueco() {
    translate([x_div1 - 1, pc_y, pc_z]) rotate([0, 90, 0]) cylinder(d = pc_d, h = 2*t + gap_aire + 2);
}
module paso_cables_tubo() {
    difference() {
        translate([x_div1, pc_y, pc_z]) rotate([0, 90, 0]) cylinder(d = pc_d + 2.4, h = 2*t + gap_aire);
        translate([x_div1 - 1, pc_y, pc_z]) rotate([0, 90, 0]) cylinder(d = pc_d, h = 2*t + gap_aire + 2);
    }
}

/* ---------- HC-SR04 ---------- */
module hcsr04_agujeros() {
    for (s = [-1, 1]) translate([scx + s*sr_sep/2, scy, -1]) cylinder(d = sr_d, h = piso + 2, $fn = 64);
}
module hcsr04_postes() {
    for (sx = [-1, 1], sy = [-1, 1])
        translate([scx + sx*sr_holes[0]/2, scy + sy*sr_holes[1]/2, piso - 0.01])
            difference() { cylinder(d = 3.6, h = sr_alto - piso); cylinder(d = 1.4, h = sr_alto); }
}

/* ---------- Pedestales DHT11 / BMP280 ---------- */
module pedestal(sz, agujero) {
    difference() {
        translate([-sz[0]/2, -sz[1]/2, piso - 0.01]) cube([sz[0], sz[1], ped_h]);
        translate([agujero, 0, piso + 2]) cylinder(d = 2.6, h = ped_h);
    }
}
module pedestales() {
    translate([scx, scy + 32, 0]) pedestal(dht_ped, -dht_ped[0]/2 + 3.5);
    translate([scx, scy - 32, 0]) pedestal(bmp_ped, 0);
}

/* =========================== TAPA =========================== */
alero = 8; faldon_h = 4;
module contorno_tapa() {
    offset(r = 3) offset(delta = -3) translate([-alero, -alero]) square([out_x + 2*alero, out_y + 2*alero]);
}
module labio(lx, ly) {
    difference() { cube([lx, ly, labio_h]); translate([1.6, 1.6, -1]) cube([lx - 3.2, ly - 3.2, labio_h + 2]); }
}
module tapa() {
    difference() {
        union() {
            linear_extrude(tapa_t) contorno_tapa();
            translate([0, 0, -faldon_h]) linear_extrude(faldon_h + 0.01)
                difference() { contorno_tapa(); offset(delta = -1.6) contorno_tapa(); }
            translate([t + tol, t + tol, -labio_h])      labio(e_x - 2*tol, in_y - 2*tol);
            translate([x_sens + tol, t + tol, -labio_h]) labio(sens_x - 2*tol, in_y - 2*tol);
            for (sx = [-1, 1], sy = [-1, 1])
                translate([dcx + sx*disp_holes[0]/2, dcy + sy*disp_holes[1]/2, -disp_alto])
                    cylinder(d = 5, h = disp_alto + 0.01);
        }
        for (p = esquinas()) translate([p[0], p[1], -1]) {
            cylinder(d = tor_lib, h = tapa_t + 2);
            translate([0, 0, tapa_t + 1 - 1.6]) cylinder(d1 = tor_lib, d2 = 6.4, h = 1.61);
        }
        for (sx = [-1, 1], sy = [-1, 1])
            translate([dcx + sx*disp_holes[0]/2, dcy + sy*disp_holes[1]/2, -disp_alto - 1])
                cylinder(d = 2.2, h = disp_alto + tapa_t - 0.6);
        // Ventana de la pantalla + rebaje para acrílico de 2 mm
        translate([dcx + disp_off[0], dcy + disp_off[1], 0]) {
            translate([0, 0, tapa_t/2 - 1]) cube([disp_ventana[0], disp_ventana[1], tapa_t + 2.01], center = true);
            translate([0, 0, tapa_t - 0.6]) cube([disp_ventana[0] + 8, disp_ventana[1] + 8, 1.21], center = true);
        }
        // Marca grabada en la tapa (0.8 mm)
        translate([t + e_x/2, t + 32, tapa_t - 0.8]) linear_extrude(1)
            text(marca, size = 8, halign = "center", valign = "center", font = "Liberation Sans:style=Bold");
        // Fotorresistencia
        translate([t + 42, t + 12, -labio_h - 1]) cylinder(d = ldr_d, h = tapa_t + labio_h + 2);
        // Panel solar: cajeado + paso del cable bajo el panel
        translate([scx - panel[0]/2 - 0.3, scy - panel[1]/2 - 0.3, tapa_t - panel_rebaje])
            cube([panel[0] + 0.6, panel[1] + 0.6, panel_rebaje + 1]);
        translate([scx, scy, -labio_h - 1]) cylinder(d = 7, h = tapa_t + labio_h + 2);
    }
}
module tapa_impresion() { translate([0, out_y, tapa_t]) rotate([180, 0, 0]) tapa(); }

/* ======================= Referencias visuales ======================= */
module fantasmas() {
    color("Peru", 0.9) translate([baq_x0, baq_y0, piso + baq_h]) cube([baq[0], baq[1], 1.6]);         // baquela
    color("Black") for (dy = [1, esp[1] - 3.5])
        translate([esp_x0 + 1, esp_y0 + dy, piso + baq_h + 1.6]) cube([esp[0] - 2, 2.5, header_h]);  // pines hembra
    color("RoyalBlue") translate([esp_x0, esp_y0, esp_z0]) cube([esp[0], esp[1], 1.6]);                // ESP32
    color("Silver") translate([esp_x0 + esp[0] - 20, esp_y0 + 4.5, esp_z0 + 1.6]) cube([18, 19, 3.2]); // módulo WROOM
    color("Silver") translate([esp_x0 - 1, usb_y - 4, esp_z0 + 1.6]) cube([6, 8, 3]);                  // USB
    color("Red")   translate([baq_x0 + 4,  baq_y0 + 2, piso + baq_h + 1.6]) cube([26, 17, 5]);          // TP4056
    color("Teal")  translate([baq_x0 + 32, baq_y0 + 2, piso + baq_h + 1.6]) cube([36, 17, 7]);          // elevador 5V
    color("DimGray") translate([bat_x0, bat_y0, piso]) cube(bat);                                        // 2x18650
    color("Blue", 0.8) translate([scx - 22.5, scy - 10, sr_alto]) cube([45, 20, 1.6]);                   // HC-SR04
    color("Silver") for (s = [-1, 1]) translate([scx + s*13, scy, 0]) cylinder(d = 16, h = sr_alto);
    color("DeepSkyBlue") translate([scx - 14, scy + 32 - 6, piso + ped_h]) cube([28, 12, 6]);            // DHT11
    color("Purple") translate([scx - 7.5, scy - 32 - 6, piso + ped_h]) cube([15, 11.5, 2]);              // BMP280
    color("Navy") translate([scx - 25, scy - 25, out_z + tapa_t - panel_rebaje + 0.02]) cube([50, 50, 2.5]);  // panel
    color("Black") translate([dcx - disp_pcb[0]/2, dcy - disp_pcb[1]/2, out_z - disp_alto - 1.6]) cube([disp_pcb[0], disp_pcb[1], 1.6]);
}

/* =========================== Salida =========================== */
if (part == "base") base();
else if (part == "tapa") tapa_impresion();
else if (part == "impresion") { base(); translate([out_x + 25, 0, 0]) tapa_impresion(); }
else if (part == "conjunto") {
    base();
    fantasmas();
    color("SkyBlue", 0.5) translate([0, 0, out_z + 0.01]) tapa();
}

echo(str("Medidas exteriores (sin orejas ni alero): ", out_x, " x ", out_y, " x ", out_z + tapa_t, " mm"));
