# E-Waves Wavey-tips

QR-tips fra E-Waves-arrangementer. Deltakerne snakker inn eller skriver et tips på mobilen. Gemini transkriberer og anonymiserer tipset, og admin godkjenner det i WordPress. Godkjente tips sendes til Waveys kunnskapsbase (Gemini File Search Store).

## Installering (test på staging først)

1. WordPress-admin: **Utvidelser → Legg til ny → Last opp utvidelse**, velg `ewaves-wavey-tips.zip` og aktiver den.
2. **Innstillinger → Wavey-tips**: lim inn Gemini API-nøkkelen og File Search Store, altså de samme verdiene som i Waveys `.env`. Klikk **Test tilkoblingen til Wavey**.
   - Det tryggeste er å legge nøkkelen i `wp-config.php` i stedet: `define( 'WAVEY_GEMINI_API_KEY', '...' );`
3. Lag en side med adressen `/tips` og innholdet `[wavey_tips]`. Skjul den gjerne fra menyen.
4. **Wavey-tips → QR-koder**: skriv inn arrangementet, for eksempel «Høstsamling 2026», og last ned QR-koden som SVG.

## Daglig bruk

- Nye tips havner under **Wavey-tips** med status «Venter på gjennomgang».
- Åpne tipset, rett opp teksten om nødvendig, og klikk **Publiser**. Da sendes tipset til Wavey, og kolonnen «Wavey» viser «✓ Sendt».
- Hvis sendingen feiler, settes tipset tilbake til «Venter», og feilmeldingen vises.
- Tips som ikke skal brukes, slettes. Tips som allerede er sendt, må også slettes i Waveys adminpanel.

## Personvern og sikkerhet

- Lydopptak lagres aldri. De slettes rett etter transkripsjon.
- Navn på personer og bedrifter fjernes av Gemini, og admin godkjenner alt før det publiseres.
- Maks 5 tips per time per IP-adresse. IP-adressen lagres bare som en hash.
- Samtykke kreves før innsending.
