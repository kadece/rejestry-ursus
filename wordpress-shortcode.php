<?php
/**
 * Plugin Name: Wykazy Ursus
 * Description: Shortcode [wykazy_ursus] (iframe z auto-wysokością) oraz [wykazy_ursus_tabela] (natywne tabele z plików JSON).
 * Version:     1.0
 * Author:      BiZU — Bezpieczny i Zielony Ursus
 * License:     GPL-2.0-or-later
 *
 * Instalacja: wgraj ten plik do wp-content/mu-plugins/ (utwórz katalog,
 * jeśli nie istnieje) albo wklej jego treść do wtyczki "Code Snippets".
 *
 * Użycie:
 *   [wykazy_ursus src="https://zielonyursus.pl/wykazy/index.html"]
 *   [wykazy_ursus_tabela rok="2026"]
 *   [wykazy_ursus_tabela rok="2026" rejestr="dec_wz" limit="20"]
 */

if (!defined('ABSPATH')) {
    exit;
}

/**
 * [wykazy_ursus] — ramka z wygenerowaną stroną.
 *
 * Strona sama zgłasza swoją wysokość przez postMessage, więc ramka nie ma
 * wewnętrznego paska przewijania. Parametr ?embed=1 ukrywa duży nagłówek
 * (na WordPressie mamy własny tytuł), zostawia przełącznik roczników.
 */
function wykazy_ursus_iframe($atts)
{
    $a = shortcode_atts([
        'src'    => '',
        'height' => '1400',
        'title'  => 'Wykazy i rejestry — Dzielnica Ursus',
    ], $atts, 'wykazy_ursus');

    if (empty($a['src'])) {
        return '<p class="wykazy-ursus-error">Shortcode [wykazy_ursus] wymaga atrybutu src.</p>';
    }

    $src = add_query_arg('embed', '1', $a['src']);
    $id  = 'wykazyUrsusFrame' . wp_rand(1000, 9999);
    $h   = max(400, (int) $a['height']);

    ob_start();
    ?>
    <div class="wykazy-ursus-embed">
      <iframe id="<?php echo esc_attr($id); ?>"
              src="<?php echo esc_url($src); ?>"
              title="<?php echo esc_attr($a['title']); ?>"
              loading="lazy"
              style="width:100%;height:<?php echo $h; ?>px;border:0;display:block;border-radius:16px;background:#f4f6f9;"></iframe>
    </div>
    <script>
    (function () {
      var f = document.getElementById(<?php echo wp_json_encode($id); ?>);
      if (!f) return;
      window.addEventListener('message', function (e) {
        if (!e.data || e.data.type !== 'wykazy-ursus-height') return;
        var h = parseInt(e.data.height, 10);
        if (h > 200) f.style.height = h + 'px';
      });
    })();
    </script>
    <?php
    return ob_get_clean();
}
add_shortcode('wykazy_ursus', 'wykazy_ursus_iframe');


/**
 * [wykazy_ursus_tabela] — natywne tabele z data/wykazy-<rok>.json.
 *
 * Atrybuty:
 *   rok     — rocznik, domyślnie bieżący
 *   rejestr — id rejestru (np. dec_wz, dec_pnb, zgl); bez tego wszystkie
 *   limit   — maksymalna liczba wierszy na rejestr, 0 = bez limitu
 */
function wykazy_ursus_tabela($atts)
{
    $a = shortcode_atts([
        'rok'     => '',
        'rejestr' => '',
        'limit'   => '0',
    ], $atts, 'wykazy_ursus_tabela');

    $rok  = $a['rok'] !== '' ? (int) $a['rok'] : (int) current_time('Y');
    $path = WP_CONTENT_DIR . '/uploads/wykazy/wykazy-' . $rok . '.json';

    if (!file_exists($path)) {
        return '<p class="wykazy-ursus-error">Brak danych dla roku '
            . esc_html((string) $rok) . '.</p>';
    }

    $d = json_decode((string) file_get_contents($path), true);
    if (!is_array($d) || empty($d['registers'])) {
        return '<p class="wykazy-ursus-error">Nieczytelny plik danych.</p>';
    }

    $limit = max(0, (int) $a['limit']);
    $want  = sanitize_key($a['rejestr']);

    ob_start();
    echo '<div class="wykazy-ursus">';

    foreach ($d['registers'] as $reg) {
        if ($want !== '' && $reg['id'] !== $want) {
            continue;
        }

        $rows = $reg['rows'];
        $more = 0;
        if ($limit > 0 && count($rows) > $limit) {
            $more = count($rows) - $limit;
            $rows = array_slice($rows, 0, $limit);
        }

        echo '<h3>' . esc_html($reg['name']) . ' <small>(' . esc_html((string) $rok) . ')</small></h3>';

        if (!$rows) {
            echo '<p>Brak pozycji.</p>';
            continue;
        }

        echo '<table class="wp-block-table wykazy-ursus-tabela"><thead><tr>';
        echo '<th>Data</th>';
        foreach ($reg['cols'] as $c) {
            echo '<th>' . esc_html($c['l']) . '</th>';
        }
        echo '</tr></thead><tbody>';

        foreach ($rows as $row) {
            echo '<tr>';
            echo '<td>' . esc_html($row['d'] ? $row['d'] : '—') . '</td>';
            foreach ($reg['cols'] as $c) {
                $v = isset($row['c'][$c['k']]) ? $row['c'][$c['k']] : '';
                echo '<td>' . esc_html($v) . '</td>';
            }
            echo '</tr>';
        }

        echo '</tbody></table>';

        if ($more > 0) {
            echo '<p><em>…i ' . (int) $more . ' więcej pozycji w tym rejestrze.</em></p>';
        }
    }

    echo '<p class="wykazy-ursus-source"><small>Źródło: '
        . '<a href="' . esc_url($d['source']) . '" target="_blank" rel="noopener">'
        . 'ursus.um.warszawa.pl</a>, stan na ' . esc_html($d['generated']) . '.</small></p>';

    echo '</div>';
    return ob_get_clean();
}
add_shortcode('wykazy_ursus_tabela', 'wykazy_ursus_tabela');
