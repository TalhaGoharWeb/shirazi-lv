"""
3D avatar acceptance tests.

  1. is_3d_available() reflects reality (WebEngine + model file).
  2. The Iron Man GLB parses in the REAL Three.js GLTFLoader (node).
  3. Vendored Three.js files are complete (importmap targets exist).
  4. The avatar HTML's JS is syntactically valid.
  5. Avatar3D degrades gracefully without WebEngine.
  6. hud_style "3d" is accepted and no longer coerced when available.
"""
import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent.parent  # shirazi-lv/
_NODE = shutil.which("node")


class Availability(unittest.TestCase):
    def test_is_3d_available_matches_reality(self):
        from core.avatar3d import is_3d_available
        from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa
        model = _HERE / "assets" / "avatar" / "ironman.glb"
        html = _HERE / "ui" / "avatar3d.html"
        self.assertTrue(model.is_file(), "ironman.glb must ship")
        self.assertTrue(html.is_file(), "avatar3d.html must ship")
        self.assertTrue(is_3d_available())

    def test_config_manager_delegates(self):
        from memory import config_manager as cm
        from core.avatar3d import is_3d_available as real
        self.assertEqual(cm.is_3d_available(), real())


class VendoredThree(unittest.TestCase):
    def test_importmap_targets_exist(self):
        self.assertTrue((_HERE / "ui" / "three" / "three.module.js").is_file())
        self.assertTrue((_HERE / "ui" / "three" / "addons" / "loaders"
                         / "GLTFLoader.js").is_file())
        self.assertTrue((_HERE / "ui" / "three" / "addons" / "utils"
                         / "BufferGeometryUtils.js").is_file())

    def test_js_syntax_valid(self):
        if _NODE is None:
            self.skipTest("node not installed")
        html = (_HERE / "ui" / "avatar3d.html").read_text()
        m = re.search(r'<script type="module">(.*?)</script>', html, re.S)
        self.assertIsNotNone(m)
        p = Path("/tmp/avatar3d_check.mjs")
        p.write_text(m.group(1))
        r = subprocess.run([_NODE, "--check", str(p)],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_glb_parses_in_real_gltfloader(self):
        if _NODE is None:
            self.skipTest("node not installed")
        t3 = Path("/tmp/t3")
        if not (t3 / "package" / "build" / "three.module.js").is_file():
            self.skipTest("three npm pack not available")
        script = t3 / "avatar3d_glb_test.mjs"
        script.write_text(
            "import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';\n"
            "import { readFileSync } from 'fs';\n"
            "globalThis.self = globalThis;\n"
            f"const buf = readFileSync('{_HERE / 'assets' / 'avatar' / 'ironman.glb'}');\n"
            "new GLTFLoader().parse(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.length), '',\n"
            "  (gltf) => { let b=0; gltf.scene.traverse(o=>{if(o.isBone)b++;});\n"
            "    console.log('OK anims=' + gltf.animations.length + ' bones=' + b); },\n"
            "  (e) => { console.error('FAIL ' + (e && e.message)); process.exit(1); });\n")
        r = subprocess.run([_NODE, str(script)], capture_output=True, text=True,
                           timeout=120, cwd=str(t3))
        self.assertEqual(r.returncode, 0, r.stderr[-500:])
        self.assertIn("OK", r.stdout)


class Avatar3DWrapper(unittest.TestCase):
    def test_graceful_without_webengine(self):
        import core.avatar3d as a3d
        real = a3d._QW
        try:
            a3d._QW = None
            av = a3d.Avatar3D()
            self.assertFalse(av.available())
            av.set_state("SPEAKING")  # must not raise
            av.set_amp(0.9)
            av.show(); av.hide()
            self.assertFalse(a3d.is_3d_available())
        finally:
            a3d._QW = real

    def test_hud_style_accepts_3d(self):
        from memory import config_manager as cm
        self.assertIn("3d", cm.HUD_STYLES)
        cm.save_hud_style("3d")
        try:
            self.assertEqual(cm.get_hud_style(), "3d")
        finally:
            cm.save_hud_style("core")


if __name__ == "__main__":
    unittest.main(verbosity=1)


class TransparentPage(unittest.TestCase):
    def test_page_background_set_transparent(self):
        """The white-rectangle bug: QWebEnginePage defaults to a WHITE
        background, which paints over the transparent WebGL canvas.
        avatar3d.py must set it transparent or the 3D view shows a
        blank white box."""
        src = (_HERE / "core" / "avatar3d.py").read_text()
        self.assertIn("setBackgroundColor", src,
                      "page background must be set explicitly")
        # must be a fully transparent color, not white/opaque
        self.assertRegex(src, r"setBackgroundColor\(QColor\(0,\s*0,\s*0,\s*0\)\)",
                         "page background must be transparent (0,0,0,0)")
