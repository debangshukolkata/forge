# 8. Matching the feel of a named product (reference styles)
When the request names a product ("like Stripe", "Linear-style", "Airbnb feel"), look for its design system first
instead of guessing. The community repository awesome-design-md holds a `DESIGN.md` per site (exact colours, type
scale, radii, shadows, component specs, do's and don'ts), for example:
`https://raw.githubusercontent.com/VoltAgent/awesome-design-md/main/design-md/<slug>/DESIGN.md` with slugs such as
stripe, linear.app, airbnb, notion, apple, vercel, supabase, spotify, revolut, wise, shopify, figma, framer, raycast,
resend, cal, posthog, claude, mistral.ai, tesla. Fetch it with `web_fetch` (it may be unreachable on a company
network: then say so and work from what you know). Take the principles and token values that give the feel (type
scale, spacing, depth, component shapes) and write them into the project's own DESIGN.md. Do not copy the brand's
logo, name, imagery or exact identity: the result must still be this product, with its own palette decision and copy.
Never ask the user which style to use: pick, say why in one line, build.
