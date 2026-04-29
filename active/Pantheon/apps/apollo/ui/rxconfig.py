import reflex as rx

config = rx.Config(
    app_name="ui",
    frontend_package_manager="npm",        # ← This forces npm (Node.js) instead of Bun
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)