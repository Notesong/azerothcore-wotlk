# Auctioneer 5.8 posting compatibility patch

The Auctioneer 5.8.4723 posting engine calls the older three-argument
`StartAuction(bid, buyout, duration)` interface. The installed 3.3.5 client uses
five arguments: bid, buyout, duration, stack size and number of stacks.

This one-line patch passes the already prepared request's stack size and exactly
one auction. Auctioneer already queues each requested stack separately. Minimum
bid, buyout, duration, item signature and the full random-property item link are
preserved.

Bid and buyout remain totals for one stack. The client's own AuctionUI multiplies
unit prices by the stack size before calling this API, so this patch leaves
Auctioneer's existing per-stack request prices unchanged.

Submitting a call does not prove that the auction was created. The existing
bag-clear confirmation, timeout failure and queue behavior remain in place.
The patch does not retry a timed-out post or declare success from the item name.
After loading it, verify the result of your next intended post in your Auctions
tab before trying again if an error appears.

The reported failure left the original item in inventory with no active owner
auction. The API mismatch is verified in the actual client AuctionUI source.

November 1 status: the one-file `CorePost.lua` update is installed with a private
backup. Five offline posting-queue checks pass against the installed file.
The user confirmed that the retried wraps listing posted successfully. Read-only
server verification found exactly one auction for the original item, with its
random property retained and no remaining inventory row. Posting larger stacks
is covered offline but has not yet been verified in play.

## Apply

Back up `Interface/AddOns/Auc-Advanced/CorePost.lua`. Apply
the zero-context patch from the `Auc-Advanced` folder:

```powershell
git apply --unidiff-zero 'C:/path/to/posting-api.patch'
```

Then use `/reload` or restart the client. No server restart, database update,
price adjustment or change to your posting settings is required.

This package contains a patch and offline checks, not the full Auctioneer addon
or its databases. Auctioneer is credited to **Norganna's AddOns**; the original
`CorePost.lua` identifies revision 4696 and Nechckn. Its header licenses that
source under GNU GPL version 2 or later. Retain the original licensing notices.
The API argument correction and regression checks are authored for this local
integration.

## Offline checks

Use Python with `lupa.lua51`. The checks load the selected addon's actual
`CorePost.lua` and run its posting queue with mocked WoW services. The mock records
API arguments; it never posts an auction. Only an explicit fixture bag change
can satisfy the normal confirmation path.

```powershell
$env:AUCTIONEER_ADDON_PATH = 'C:/path/to/Auc-Advanced'
# Optional when lupa is installed in an isolated folder:
$env:LUPA_RUNTIME_PATH = 'C:/path/to/lua-runtime'
python tests/test_corepost.py
```

Five checks cover a single random-property item, a prepared stack of several
items, delayed confirmation, timeout without retry, and a separate queued entry.
The original file fails the two API-contract cases. The patched file passes all
five; both versions retain the three confirmation and queue checks.
