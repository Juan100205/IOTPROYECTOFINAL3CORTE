// =====================================================================
//  WaterGuard v2.0 - Soporte para tanque (OPCIONAL, aparte de la caja)
//  Toma las medidas de estacion_pi5_v2.scad, así siempre coinciden.
//
//  vista = "conjunto_tanque" : la caja montada en el tanque
//          "soporte_borde" / "soporte_tapa" : STL por si algún día lo imprimen
//          "plantilla" : dibujo 2D 1:1 para hacerlo a mano
// =====================================================================
include <waterguard_esp32.scad>
part = "ninguno";   // apaga la salida del archivo principal

vista = "conjunto_tanque"; // [conjunto_tanque, soporte_borde, soporte_tapa, plantilla]
montaje = "borde"; // [borde, tapa]

if (vista == "soporte_borde") soporte_impresion("borde");
else if (vista == "soporte_tapa") soporte_impresion("tapa");
else if (vista == "conjunto_tanque") escena_tanque();
else if (vista == "plantilla") plantilla();

/* ===================== SOPORTE PARA TANQUE ===================== */
// La caja se atornilla encima (6x M3x16 por abajo, en las orejas).
// Bajo el HC-SR04 sale una bocina abierta que lo protege de salpicaduras;
// abre 20° (más que el haz de 15° del sensor) para no dar ecos falsos.
// La placa tapa las ranuras del piso: el aire húmedo del tanque no entra
// a la cámara de sensores (solo respira por las persianas laterales).
//
//  "borde": abraza la pared del tanque y se aprieta con 2 tornillos M5
//           desde afuera. Para tanques abiertos, cisternas o albercas.
//  "tapa":  se atornilla sobre la tapa del tanque (4x M4 cabeza plana);
//           se corta en la tapa un hueco para la bocina.

sop_t      = 6;     // grosor de la placa
brazo      = 40;    // la placa sale por delante: aleja el sensor de la pared
pared_max  = 20;    // grosor máximo de pared del tanque que admite
pestana_h  = 35;    // alto de las pestañas que abrazan la pared
apriete_d  = 5.4;   // tornillos M5 de apriete
bocina_l   = 25;    // largo de la bocina bajo la placa
bocina_ang = 20;    // apertura de la bocina
r_tr       = 9.5;   // radio interior junto a cada transductor
r_bot      = r_tr + (sop_t + bocina_l) * tan(bocina_ang);
ds_guia    = 22;    // largo de la guía del cable bajo la placa
ds_largo   = 180;   // largo de cable colgando (solo para la vista)

module huella2d() {
    square([out_x, out_y]);
    for (p = esquinas()) translate(p) circle(d = oreja_d);
}
module perfil_bocina(r) { hull() for (s = [-1, 1]) translate([s*sr_sep/2, 0]) circle(r, $fn = 64); }

module soporte(modo) {
    y_canal = -brazo + 8;                 // cara exterior de la pared del tanque
    y_int   = y_canal + pared_max;        // pestaña interior
    difference() {
        union() {
            // Placa
            translate([0, 0, -sop_t]) linear_extrude(sop_t) {
                huella2d();
                if (modo == "borde") translate([-oreja_d/2, -brazo]) square([out_x + oreja_d, brazo + 1]);
            }
            // Bocina (exterior)
            translate([scx, scy, 0]) hull() {
                translate([0, 0, -0.01]) linear_extrude(0.01) perfil_bocina(r_tr + 2);
                translate([0, 0, -sop_t - bocina_l]) linear_extrude(0.01) perfil_bocina(r_bot + 2);
            }
            if (modo == "borde") {
                // Pestaña exterior (lleva los tornillos de apriete)
                translate([-oreja_d/2, -brazo, -sop_t - pestana_h]) cube([out_x + oreja_d, 8, pestana_h + 0.01]);
                // Pestaña interior
                translate([-oreja_d/2, y_int, -sop_t - pestana_h + 10]) cube([out_x + oreja_d, 5, pestana_h - 10 + 0.01]);
                // Nervios de refuerzo bajo la placa (dentro del tanque)
                for (x = [18, out_x - 22])
                    translate([x, y_int, -sop_t - 12]) cube([4, out_y - y_int - 10, 12.01]);
            }
            // Guía del cable del DS18B20 (con ranura para precinto/abrazadera plástica)
            translate([ds_x, ds_y, -sop_t - ds_guia + 0.01]) cylinder(d = 11, h = ds_guia);
        }
        // Interior de la bocina
        translate([scx, scy, 0]) hull() {
            translate([0, 0, 1]) linear_extrude(0.01) perfil_bocina(r_tr);
            translate([0, 0, -0.01]) linear_extrude(0.01) perfil_bocina(r_tr);
            translate([0, 0, -sop_t - bocina_l - 0.01]) linear_extrude(0.01) perfil_bocina(r_bot);
        }
        // Canal para silicona alrededor de los transductores (sella contra la caja)
        translate([scx, scy, -1]) linear_extrude(1.01)
            difference() { perfil_bocina(r_tr + 5); perfil_bocina(r_tr + 3); }
        // Tornillos M3 a las orejas de la caja (avellanados por abajo)
        for (p = esquinas()) translate([p[0], p[1], -sop_t - 1]) {
            cylinder(d = 3.4, h = sop_t + 2);
            cylinder(d1 = 6.6 + 2, d2 = 3.4, h = 1 + 1.7);
        }
        if (modo == "borde") {
            // Tornillos de apriete M5 con tuerca embutida por fuera
            for (x = [out_x * 0.25, out_x * 0.75])
                translate([x, -brazo - 1, -sop_t - pestana_h / 2]) rotate([-90, 0, 0]) {
                    cylinder(d = apriete_d, h = 10);
                    rotate([0, 0, 30]) cylinder(d = 9.6, h = 1 + 4, $fn = 6);
                }
            // Marca grabada en el brazo (queda a la vista, fuera del tanque)
            translate([out_x/2 + 6, -brazo/2 - 4, -0.8]) linear_extrude(1)
                text(marca, size = 8, halign = "center", valign = "center",
                     font = "Liberation Sans:style=Bold");
            // Gota
            translate([out_x/2 - 46, -brazo/2 - 4.5, -0.8]) linear_extrude(1)
                hull() { circle(r = 3.2); translate([0, 6]) circle(r = 0.3); }
        }
        // Paso del cable del DS18B20: la sonda cuelga hasta el agua
        translate([ds_x, ds_y, -sop_t - ds_guia - 1]) cylinder(d = ds_cable_d + 0.6, h = sop_t + ds_guia + 2);
        // Ranura para el precinto que sujeta el cable
        translate([ds_x - 7, ds_y - 0.9, -sop_t - ds_guia + 6]) cube([14, 1.8, 4]);
        if (modo == "tapa")
            for (x = [20, out_x - 14], y = [14, out_y - 14])
                translate([x, y, -sop_t - 1]) {
                    cylinder(d = 4.4, h = sop_t + 2);
                    translate([0, 0, sop_t + 1 - 2.4]) cylinder(d1 = 4.4, d2 = 8.8, h = 2.41);
                }
    }
}
// Se imprime boca abajo: la cara donde apoya la caja va sobre la cama.
module soporte_impresion(modo) { translate([0, 0, 0]) rotate([180, 0, 0]) soporte(modo); }

echo(str("Modo tapa: hueco en la tapa del tanque de ",
         sr_sep + 2*(r_bot + 2) + 2, " x ", 2*(r_bot + 2) + 2, " mm (óvalo)"));


/* ===================== Escena: montado en el tanque ===================== */
nivel_agua = -200;   // superficie del agua (solo para la vista)
module sonda_ds() {
    color("Black")  translate([ds_x, ds_y, -sop_t - ds_largo]) cylinder(d = 4, h = ds_largo);
    color("Silver") translate([ds_x, ds_y, -sop_t - ds_largo - 50]) cylinder(d = 6, h = 50);
}
module escena_tanque(con_ds = true) {
    color("LightGray") soporte(montaje);
    base();
    fantasmas();
    color("SkyBlue", 0.5) translate([0, 0, out_z + 0.01]) tapa();
    if (con_ds) sonda_ds();
    // Haz del HC-SR04 hasta el agua (15°)
    color("Gold", 0.35) for (s = [-1, 1]) translate([scx + s*sr_sep/2, scy, nivel_agua])
        cylinder(r1 = 8 + (-nivel_agua) * tan(7.5), r2 = 8, h = -nivel_agua);
    // Tanque de referencia
    if (montaje == "borde") {
        color("Gainsboro", 0.6) translate([-40, -brazo + 8 + 2, -300]) cube([out_x + 80, 12, 300 - sop_t]);
    } else {
        color("Gainsboro", 0.6) translate([0, 0, -sop_t - 4]) linear_extrude(4) difference() {
            translate([-60, -60]) square([out_x + 120, out_y + 120]);
            translate([scx, scy]) perfil_bocina(r_bot + 3);
            translate([ds_x, ds_y]) circle(d = 7);
        }
    }
    color("DodgerBlue", 0.35) translate([-40, -brazo + 22, -300]) cube([out_x + 80, out_y + brazo + 40, 300 + nivel_agua]);
}


/* ===================== Plantilla 1:1 para hacerlo a mano ===================== */
module plantilla() {
    difference() { huella2d(); offset(delta = -0.5) huella2d(); }           // contorno de la caja
    translate([scx, scy]) difference() { perfil_bocina(r_tr); perfil_bocina(r_tr - 0.5); }  // hueco HC-SR04
    for (s = [-1, 1]) translate([scx + s*sr_sep/2, scy]) cruz(5);
    for (p = esquinas()) translate(p) { circulo_linea(3.4); cruz(4); }    // tornillos M3
    translate([ds_x, ds_y]) { circulo_linea(ds_cable_d + 1); cruz(5); }   // cable DS18B20
    translate([scx, scy - r_tr - 6]) text("HC-SR04: cortar este ovalo", size = 3.5, halign = "center");
    translate([ds_x, ds_y + 6]) text("DS18B20: 6 mm", size = 3, halign = "center");
    translate([t + e_x/2, out_y - 22]) text("Agujeros de 3.4 mm (M3) en las 6 orejas", size = 3, halign = "center");
    translate([out_x/2, -9]) text("^ FRENTE DE LA CAJA (LEDs) ^", size = 3.5, halign = "center");
    translate([out_x/2, -18]) text(str(marca, " - plantilla tamano real"), size = 4.5, halign = "center");
    translate([out_x/2 - 25, -27]) { square([50, 1]); square([0.6, 4]); translate([49.4, 0]) square([0.6, 4]); }
    translate([out_x/2, -33]) text("esta raya debe medir 50 mm", size = 3, halign = "center");
}
module circulo_linea(d) { difference() { circle(d = d); circle(d = d - 0.8); } }
module cruz(l) { square([l, 0.3], center = true); square([0.3, l], center = true); }
