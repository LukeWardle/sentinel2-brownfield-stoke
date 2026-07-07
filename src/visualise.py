"""
visualise.py — False Colour Map, Results Report and Interactive Map
====================================================================
Provides four functions for visualising pipeline results. convert_k_to_rgb
normalises PCA components to RGB values. false_map_creation reconstructs
and saves the false colour map. report_creation generates a professional
PDF report for planning officials. create_interactive_map produces a
Folium interactive map with candidate sites overlaid on OpenStreetMap.
"""
import os
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import folium
from datetime import datetime
from pathlib import Path
from pyproj import Transformer
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

sys.path.insert(0, str(Path(__file__).parent.parent))


def convert_k_to_rgb(X_reduced: np.ndarray) -> np.ndarray:
    """
    Takes top 3 principal components and normalises to 0-255 range
    for RGB colour channels.

    Args:
        X_reduced (np.ndarray): Shape (pixels, k) — PCA reduced array.

    Returns:
        rgb_array (np.ndarray): Shape (pixels, 3) — normalised RGB values.

    Raises:
        ValueError: If fewer than 3 components, empty array, or zero variance.
    """
    if X_reduced.ndim != 2 or X_reduced.shape[1] < 3:
        raise ValueError(
            f"X_reduced must have at least 3 components, got shape {X_reduced.shape}"
        )
    if X_reduced.shape[0] == 0:
        raise ValueError("X_reduced is empty — no pixels to convert")

    rgb_array = np.zeros((X_reduced.shape[0], 3), dtype=np.uint8)

    for i in range(3):
        component = X_reduced[:, i]
        min_val = component.min()
        max_val = component.max()

        if max_val - min_val == 0:
            raise ValueError(f"Component {i+1} has zero variance — cannot normalise")

        normalised = (component - min_val) / (max_val - min_val) * 255
        rgb_array[:, i] = normalised.astype(np.uint8)

    return rgb_array


def false_map_creation(rgb_array: np.ndarray,
                       output_dir: str,
                       mask: np.ndarray = None,
                       original_shape: tuple = None) -> None:
    """
    Reconstructs the full 2D image and saves as a false colour map PNG.

    Args:
        rgb_array (np.ndarray): Shape (pixels, 3) — RGB values.
        output_dir (str): Directory to save the output file.
        mask (np.ndarray, optional): Boolean mask from mask_nodata.
        original_shape (tuple, optional): Original 2D shape (height, width).

    Returns:
        None — saves false_colour_map_YYYYMMDD_HHMMSS.png to output_dir.
    """
    if mask is not None and original_shape is not None:
        image_2d = np.zeros((original_shape[0], original_shape[1], 3), dtype=np.uint8)
        image_2d[mask.reshape(original_shape)] = rgb_array
    else:
        side = int(np.sqrt(rgb_array.shape[0]))
        image_2d = rgb_array[:side * side].reshape(side, side, 3)

    fig, ax = plt.subplots(1, 1, figsize=(10, 10))
    ax.imshow(image_2d)
    ax.axis('off')
    ax.set_title('Sentinel-2 False Colour Map — Spectral PCA', fontsize=14, pad=20)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"false_colour_map_{timestamp}.png"
    filepath = os.path.join(output_dir, filename)
    plt.savefig(filepath, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"False colour map saved to {filepath}")


def report_creation(k: int,
                    sorted_eigenvalues: np.ndarray,
                    output_dir: str,
                    gss_code: str,
                    image_date: str,
                    candidate_sites: list,
                    change_detection: dict) -> None:
    """
    Generates a professional PDF report for planning officials summarising
    the pipeline results including PCA variance, candidate brownfield sites,
    register matching and change detection findings.

    Args:
        k (int): Number of principal components retained.
        sorted_eigenvalues (np.ndarray): Shape (n,) — eigenvalues sorted by variance.
        output_dir (str): Directory to save the PDF report.
        gss_code (str): GSS code for the council area processed.
        image_date (str): Date of the Sentinel-2 image in YYYY-MM-DD format.
        candidate_sites (list): List of dicts from calculate_site_properties
                                and register matching, each containing
                                centroid_utm_x, centroid_utm_y, pixel_count,
                                hectares, mean_bsi and matched_site_reference.
        change_detection (dict): Dict with 'added' and 'removed' lists from
                                 detect_register_changes.

    Returns:
        None — saves results_report_YYYYMMDD_HHMMSS.pdf to output_dir.

    Raises:
        ValueError: If candidate_sites is None or change_detection is missing
                    required keys.
    """
    if candidate_sites is None:
        raise ValueError("candidate_sites cannot be None")

    if not isinstance(change_detection, dict) or \
       'added' not in change_detection or 'removed' not in change_detection:
        raise ValueError("change_detection must be a dict with 'added' and 'removed' keys")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"results_report_{timestamp}.pdf"
    filepath = os.path.join(output_dir, filename)

    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=18,
        textColor=colors.HexColor('#1a1a2e'),
        spaceAfter=6,
        alignment=TA_CENTER
    )

    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#444444'),
        spaceAfter=4,
        alignment=TA_CENTER
    )

    section_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#1a1a2e'),
        spaceBefore=12,
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#333333'),
        spaceAfter=4,
        leading=14
    )

    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#888888'),
        alignment=TA_CENTER
    )

    story = []

    # --- Header ---
    story.append(Paragraph("SiteSignal Ltd", title_style))
    story.append(Paragraph("Brownfield Site Analysis Report", subtitle_style))
    story.append(Paragraph(
        f"Council: {gss_code} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"Image date: {image_date} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"Generated: {datetime.now().strftime('%d %B %Y')}",
        subtitle_style
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#1a1a2e')))
    story.append(Spacer(1, 0.3*cm))

    # --- Executive Summary ---
    matched = [s for s in candidate_sites if s.get('matched_site_reference')]
    unmatched = [s for s in candidate_sites if not s.get('matched_site_reference')]

    story.append(Paragraph("Executive Summary", section_style))
    story.append(Paragraph(
        f"This report presents the results of satellite spectral analysis of Sentinel-2 "
        f"imagery captured on {image_date} for council area {gss_code}. The analysis "
        f"identified <b>{len(candidate_sites)}</b> candidate brownfield sites, of which "
        f"<b>{len(matched)}</b> match entries on the current brownfield register and "
        f"<b>{len(unmatched)}</b> are potential unregistered brownfield sites warranting "
        f"further investigation by planning officers.",
        body_style
    ))
    story.append(Spacer(1, 0.2*cm))

    # --- Summary Statistics ---
    total_variance = sum(sorted_eigenvalues[:k]) / sum(sorted_eigenvalues) * 100
    summary_data = [
        ['Metric', 'Value'],
        ['Total candidate sites identified', str(len(candidate_sites))],
        ['Matched to brownfield register', str(len(matched))],
        ['Potential unregistered sites', str(len(unmatched))],
        ['Principal components retained (k)', str(k)],
        ['Variance explained by PCA', f"{total_variance:.1f}%"],
    ]

    summary_table = Table(summary_data, colWidths=[12*cm, 4*cm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f5f5f5'), colors.white]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 0.4*cm))

    # --- Unregistered Candidate Sites ---
    if unmatched:
        story.append(Paragraph("Potential Unregistered Brownfield Sites", section_style))
        story.append(Paragraph(
            "The following candidate sites were identified by spectral analysis but do not "
            "appear on the current brownfield register. These sites are recommended for "
            "physical verification by planning officers.",
            body_style
        ))
        story.append(Spacer(1, 0.2*cm))

        unmatched_data = [['Site ID', 'Estimated Size (ha)', 'BSI Score', 'UTM Easting', 'UTM Northing']]
        for i, site in enumerate(unmatched[:20]):
            unmatched_data.append([
                str(i + 1),
                f"{site.get('hectares', 'N/A')} ha",
                f"{site.get('mean_bsi', 0):.4f}",
                f"{site['centroid_utm_x']:.0f}",
                f"{site['centroid_utm_y']:.0f}",
            ])

        unmatched_table = Table(unmatched_data, colWidths=[2*cm, 4*cm, 3*cm, 3.5*cm, 3.5*cm])
        unmatched_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#c0392b')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#fdf2f2'), colors.white]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('PADDING', (0, 0), (-1, -1), 5),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ]))
        story.append(unmatched_table)

        if len(unmatched) > 20:
            story.append(Spacer(1, 0.2*cm))
            story.append(Paragraph(
                f"Note: {len(unmatched) - 20} additional unregistered candidate sites not "
                f"shown. Full results available in the interactive map and database.",
                body_style
            ))
        story.append(Spacer(1, 0.4*cm))

    # --- Change Detection ---
    story.append(Paragraph("Register Change Detection", section_style))

    added = change_detection.get('added', [])
    removed = change_detection.get('removed', [])

    story.append(Paragraph(
        f"Comparison of brownfield register data across available years identified "
        f"<b>{len(added)}</b> sites newly added to the register and "
        f"<b>{len(removed)}</b> sites removed (likely developed).",
        body_style
    ))

    if removed:
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph("Sites Likely Developed (removed from register):", body_style))
        removed_data = [['Site Reference', 'Address']]
        for site in removed[:10]:
            removed_data.append([
                str(site.get('site_reference', '')),
                str(site.get('name_address', ''))[:60]
            ])
        removed_table = Table(removed_data, colWidths=[4*cm, 12*cm])
        removed_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f2fdf5'), colors.white]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('PADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(removed_table)

    if added:
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph("Sites Newly Added to Register:", body_style))
        added_data = [['Site Reference', 'Address']]
        for site in added[:10]:
            added_data.append([
                str(site.get('site_reference', '')),
                str(site.get('name_address', ''))[:60]
            ])
        added_table = Table(added_data, colWidths=[4*cm, 12*cm])
        added_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2980b9')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f2f8fd'), colors.white]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('PADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(added_table)

    story.append(Spacer(1, 0.4*cm))

    # --- Disclaimer and Footer ---
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cccccc')))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        "All candidate sites identified by this system require physical verification by "
        "qualified planning officers before any planning decisions are made. Results are "
        "generated from Sentinel-2 satellite imagery and should be treated as indicative only.",
        body_style
    ))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        "Generated by SiteSignal Ltd | Sentinel-2 L2A imagery via Copernicus Data Space "
        "Ecosystem | Open Government Licence data via planning.data.gov.uk",
        footer_style
    ))

    doc.build(story)
    print(f"PDF report saved to {filepath}")


def create_interactive_map(candidate_sites: list,
                           output_dir: str,
                           gss_code: str) -> None:
    """
    Creates an interactive Folium map with OpenStreetMap base layer showing
    candidate brownfield sites as markers. Green markers indicate register-matched
    sites, red markers indicate potential unregistered brownfield. Clickable popups
    show site reference, estimated size in hectares, BSI value and register match
    status. Saves as a standalone HTML file to outputs/.

    Args:
        candidate_sites (list): List of dicts from calculate_site_properties and
                                register matching, each containing centroid_utm_x,
                                centroid_utm_y, pixel_count, hectares, mean_bsi and
                                matched_site_reference.
        output_dir (str): Directory to save the HTML file — typically outputs/.
        gss_code (str): GSS code for the council area being mapped.

    Returns:
        None — saves interactive_map_GSSODE_YYYYMMDD_HHMMSS.html to outputs/.
    """
    if not candidate_sites:
        print("No candidate sites to map — skipping interactive map generation")
        return

    utm_xs = [site['centroid_utm_x'] for site in candidate_sites]
    utm_ys = [site['centroid_utm_y'] for site in candidate_sites]
    centre_x = sum(utm_xs) / len(utm_xs)
    centre_y = sum(utm_ys) / len(utm_ys)

    transformer = Transformer.from_crs("EPSG:32630", "EPSG:4326")
    centre_lat, centre_lon = transformer.transform(centre_x, centre_y)

    m = folium.Map(location=[centre_lat, centre_lon], zoom_start=13)

    matched_count = 0
    unmatched_count = 0

    for site in candidate_sites:
        lat, lon = transformer.transform(
            site['centroid_utm_x'], site['centroid_utm_y']
        )

        matched = site.get('matched_site_reference') is not None
        marker_colour = 'green' if matched else 'red'

        if matched:
            matched_count += 1
            match_status = f"Matched to register: {site['matched_site_reference']}"
            site_type = "Registered Brownfield Site"
        else:
            unmatched_count += 1
            match_status = "Potential unregistered brownfield — verification required"
            site_type = "Unregistered Candidate Site"

        popup_html = f"""
        <div style="font-family: Arial, sans-serif; font-size: 13px; min-width: 250px;">
            <b style="font-size: 14px;">{site_type}</b><br><br>
            <b>Status:</b> {match_status}<br>
            <b>Estimated size:</b> {site.get('hectares', 'N/A')} hectares<br>
            <b>Mean BSI:</b> {site.get('mean_bsi', 0):.4f}<br><br>
            <i style="font-size: 11px; color: #666;">
                All sites require physical verification before planning decisions are made.
            </i>
        </div>
        """

        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=320),
            tooltip=f"{'✓ Registered' if matched else '⚠ Unregistered'} — click for details",
            icon=folium.Icon(color=marker_colour, icon='info-sign')
        ).add_to(m)

    # Add legend
    legend_html = f"""
    <div style="position: fixed; bottom: 30px; left: 30px; z-index: 1000;
                background-color: white; padding: 15px; border-radius: 8px;
                border: 2px solid #ccc; font-family: Arial, sans-serif; font-size: 13px;">
        <b>SiteSignal Ltd — Candidate Sites</b><br>
        <b>Council:</b> {gss_code}<br><br>
        <span style="color: green;">●</span> Matched to register ({matched_count})<br>
        <span style="color: red;">●</span> Unregistered candidate ({unmatched_count})<br><br>
        <i style="font-size: 11px; color: #666;">Click markers for details</i>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"interactive_map_{gss_code}_{timestamp}.html"
    filepath = os.path.join(output_dir, filename)
    m.save(filepath)
    print(f"Interactive map saved to {filepath}")