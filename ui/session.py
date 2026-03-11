"""
ui/session.py — Funções JS para persistência de sessão (localStorage + cookie).
"""

import streamlit.components.v1 as components


def js_save_session(token: str) -> None:
    """Salva token no localStorage E cookie (30 dias)."""
    components.html(
        f"""<!DOCTYPE html><html><head>
<style>html,body{{margin:0;padding:0;overflow:hidden;}}</style>
</head><body><script>
(function() {{
    var t = '{token}';
    try {{ window.parent.localStorage.setItem('pav_session', t); }} catch(e) {{}}
    try {{
        var exp = new Date(Date.now()+2592000000).toUTCString();
        window.parent.document.cookie = 'pav_session='+encodeURIComponent(t)+';expires='+exp+';path=/;SameSite=Lax';
    }} catch(e) {{}}
}})();
</script></body></html>""",
        height=1,
    )


def js_clear_session() -> None:
    """Remove token do localStorage e cookie."""
    components.html(
        """<!DOCTYPE html><html><head>
<style>html,body{margin:0;padding:0;overflow:hidden;}</style>
</head><body><script>
(function() {
    try { window.parent.localStorage.removeItem('pav_session'); } catch(e) {}
    try { window.parent.document.cookie='pav_session=;expires=Thu,01 Jan 1970 00:00:00 GMT;path=/'; } catch(e) {}
})();
</script></body></html>""",
        height=1,
    )
