#!/usr/bin/env python3
"""
Scientific Panel Generator - Versión Avanzada y Simplificada
Combina múltiples PDFs en un panel respetando proporciones y optimizando espacio.

Nomenclatura de Layout:
    - 'AB-C' o '2,1': Fila 1 con 2 paneles, Fila 2 con 1 panel.
    - 'ABC' o '3': 3 paneles en una sola fila.
    - 'A-B-C' o '1,1,1': 3 paneles en 3 filas (columna).
    - '2x2': Grilla automática de 2 columnas y 2 filas.
"""

import fitz  # PyMuPDF
import argparse
import sys
import os
from pathlib import Path
from typing import List, Tuple, Dict, Any

# Constante de conversión
mm = 2.83465  # 1mm = 2.83465 puntos

class PanelGenerator:
    def __init__(self, 
                 page_width: float = 180,
                 page_height: float = None,  # Si es None, se autocalcula
                 margin: float = 5,
                 spacing: float = 3,
                 label_size: int = 12):
        self.page_width_mm = page_width
        self.page_height_mm = page_height
        self.margin = margin * mm
        self.spacing = spacing * mm
        self.label_size = label_size
        
        self.usable_width = (page_width * mm) - 2 * self.margin

    def get_pdf_metrics(self, file_paths: List[str]) -> List[Dict[str, float]]:
        """Obtiene dimensiones y aspect ratio de cada PDF."""
        metrics = []
        for path in file_paths:
            try:
                doc = fitz.open(path)
                page = doc[0]
                rect = page.rect
                metrics.append({
                    'width': rect.width,
                    'height': rect.height,
                    'ratio': rect.width / rect.height if rect.height > 0 else 1.0,
                    'path': path
                })
                doc.close()
            except Exception as e:
                print(f"⚠️ Error leyendo {path}: {e}")
                metrics.append({'width': 100, 'height': 100, 'ratio': 1.0, 'path': path})
        return metrics

    def parse_layout_structure(self, layout_str: str, num_files: int) -> List[List[int]]:
        """
        Convierte el layout string en una estructura de filas y columnas.
        Ej: 'AB-C' o '2,1' -> [[0, 1], [2]] (índices de los archivos)
        """
        structure = []
        
        # Caso '2x2'
        if 'x' in layout_str.lower():
            try:
                cols, rows = map(int, layout_str.lower().split('x'))
                idx = 0
                for r in range(rows):
                    row = []
                    for c in range(cols):
                        if idx < num_files:
                            row.append(idx)
                            idx += 1
                    if row: structure.append(row)
            except ValueError:
                pass
        
        # Caso '2,1' o '2-1'
        elif ',' in layout_str or '-' in layout_str:
            sep = ',' if ',' in layout_str else '-'
            try:
                row_counts = [int(x) if x.isdigit() else len(x) for x in layout_str.split(sep)]
                idx = 0
                for count in row_counts:
                    row = []
                    for _ in range(count):
                        if idx < num_files:
                            row.append(idx)
                            idx += 1
                    if row: structure.append(row)
            except:
                pass
        
        # Caso simple 'ABC' o '3'
        else:
            if layout_str.isdigit():
                count = int(layout_str)
                structure.append(list(range(min(count, num_files))))
            else:
                structure.append(list(range(min(len(layout_str), num_files))))
                
        # Validar que todos los archivos estén
        total_in_struct = sum(len(r) for r in structure)
        if total_in_struct < num_files:
            # Agregar faltantes en una nueva fila
            remaining = list(range(total_in_struct, num_files))
            structure.append(remaining)
            
        return structure

    def calculate_layout(self, structure: List[List[int]], metrics: List[Dict]) -> Dict[str, Any]:
        """
        Calcula las alturas ideales de las filas y posiciones finales.
        """
        layout_rows = []
        
        # 1. Calcular el 'ancho relativo' de cada fila basado en el ancho total de la página
        # y cuánto alto necesitaría esa fila para que sus figuras quepan sin distorsión.
        
        row_ideal_heights = []
        for row_indices in structure:
            row_metrics = [metrics[i] for i in row_indices]
            num_panels = len(row_indices)
            
            # Espacio disponible para figuras en esta fila (puntos)
            avail_w = self.usable_width - (num_panels - 1) * self.spacing
            
            # Ancho de cada panel en la fila
            panel_w = avail_w / num_panels
            
            # Altura requerida por la figura más 'exigente' (la más alta proporcionalmente)
            # + espacio para la etiqueta (+4 puntos de margen interno)
            required_height = 0
            for m in row_metrics:
                h_at_panel_w = panel_w / m['ratio']
                required_height = max(required_height, h_at_panel_w)
            
            row_ideal_heights.append(required_height + self.label_size + 4)

        # 2. Determinar altura de página
        total_ideal_height = sum(row_ideal_heights) + (len(structure) - 1) * self.spacing + 2 * self.margin
        
        final_page_height = self.page_height_mm * mm if self.page_height_mm else total_ideal_height
        final_usable_height = final_page_height - 2 * self.margin - (len(structure) - 1) * self.spacing
        
        # 3. Escalar alturas si la página es fija
        if self.page_height_mm:
            scale_factor = final_usable_height / sum(row_ideal_heights) if sum(row_ideal_heights) > 0 else 1.0
            actual_row_heights = [h * scale_factor for h in row_ideal_heights]
        else:
            actual_row_heights = row_ideal_heights

        # 4. Generar coordenadas finales
        panel_configs = []
        current_y = self.margin
        for row_idx, row_indices in enumerate(structure):
            h = actual_row_heights[row_idx]
            num_panels = len(row_indices)
            avail_w = self.usable_width - (num_panels - 1) * self.spacing
            panel_w = avail_w / num_panels
            
            current_x = self.margin
            for i in row_indices:
                panel_configs.append({
                    'index': i,
                    'rect': fitz.Rect(current_x, current_y, current_x + panel_w, current_y + h),
                    'path': metrics[i]['path']
                })
                current_x += panel_w + self.spacing
            current_y += h + self.spacing
            
        return {
            'page_size': (self.page_width_mm * mm, final_page_height),
            'panels': panel_configs
        }

    def generate(self, layout_str: str, input_files: List[str], output_file: str, labels: List[str] = None):
        metrics = self.get_pdf_metrics(input_files)
        structure = self.parse_layout_structure(layout_str, len(input_files))
        result = self.calculate_layout(structure, metrics)
        
        pw, ph = result['page_size']
        print(f"🚀 Generando panel: {pw/mm:.1f}x{ph/mm:.1f} mm")
        
        doc_out = fitz.open()
        page_out = doc_out.new_page(width=pw, height=ph)
        
        for i, config in enumerate(result['panels']):
            rect = config['rect']
            doc_in = fitz.open(config['path'])
            page_in = doc_in[0]
            
            # Área para la figura (restando el espacio reservado para la etiqueta)
            fig_rect = fitz.Rect(rect.x0, rect.y0 + self.label_size + 4, rect.x1, rect.y1)
            
            in_rect = page_in.rect
            scale_w = fig_rect.width / in_rect.width
            scale_h = fig_rect.height / in_rect.height
            scale = min(scale_w, scale_h)
            
            # Centrar en el área disponible para la figura
            sw, sh = in_rect.width * scale, in_rect.height * scale
            dx = (fig_rect.width - sw) / 2
            dy = (fig_rect.height - sh) / 2
            dest = fitz.Rect(fig_rect.x0 + dx, fig_rect.y0 + dy, fig_rect.x0 + dx + sw, fig_rect.y0 + dy + sh)
            
            page_out.show_pdf_page(dest, doc_in, 0)
            
            # Etiqueta (en el espacio reservado justo arriba de la figura)
            txt = labels[i] if labels and i < len(labels) else chr(65 + i)
            page_out.insert_text((rect.x0, rect.y0 + self.label_size), 
                                 txt, fontsize=self.label_size, fontname="Helvetica-Bold")
            doc_in.close()
            
        # Determinar formato de salida
        ext = os.path.splitext(output_file)[1].lower()
        if ext in ['.png', '.jpg', '.jpeg', '.tiff', '.tif']:
            pix = page_out.get_pixmap(dpi=self.dpi)
            pix.save(output_file)
        elif ext == '.svg':
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(page_out.get_svg_content())
        else:
            doc_out.save(output_file)
            
        doc_out.close()
        print(f"✅ Guardado en: {output_file} (DPI: {self.dpi})")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generador de Paneles Científicos (Smart-Sizing)")
    parser.add_argument("--layout", required=True, help="Ej: '2,1' o 'AB-C'")
    parser.add_argument("--input", nargs="+", required=True, help="Archivos PDF")
    parser.add_argument("--output", required=True, help="Archivo de salida (.pdf, .png, .tiff, .svg)")
    parser.add_argument("--page-width", type=float, default=180, help="Ancho en mm")
    parser.add_argument("--page-height", type=float, help="Alto en mm (opcional, se autocalcula)")
    parser.add_argument("--margin", type=float, default=5, help="Margen en mm")
    parser.add_argument("--spacing", type=float, default=3, help="Espacio entre figuras en mm")
    parser.add_argument("--label-size", type=int, default=14, help="Tamaño de letra")
    parser.add_argument("--labels", nargs="+", help="Etiquetas personalizadas")
    parser.add_argument("--dpi", type=int, default=300, help="DPI para exportar a imagen (default: 300)")
    
    args = parser.parse_args()
    
    gen = PanelGenerator(args.page_width, args.page_height, args.margin, args.spacing, args.label_size)
    gen.dpi = args.dpi # Inyección rápida de DPI
    gen.generate(args.layout, args.input, args.output, args.labels)
