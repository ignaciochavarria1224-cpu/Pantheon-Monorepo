# BlackBook

This folder is the canonical standalone BlackBook application inside the monorepo.

It contains the imported Streamlit version of BlackBook, which is currently the real application truth for the financial system.

## Current Role

- standalone BlackBook application
- current canonical product truth for BlackBook
- source system for future Pantheon-native migration work

## Runtime Notes

- primary runtime is Streamlit
- primary database is PostgreSQL through `DATABASE_URL`
- the current live deployment model is Neon-backed
- if `DATABASE_URL` is missing, the app stops rather than silently using a different cloud backend

## Relationship To Pantheon

- `active/Pantheon/apps/blackbook` is the Pantheon-native destination
- this standalone app remains the current source of truth until Pantheon reaches feature parity

## Legacy Copy

The previous Reflex-based BlackBook copy was preserved at:

- `archive/BlackBook_Reflex_Legacy_2026-04-29`

That archive is for reference only and should not receive new product work.
