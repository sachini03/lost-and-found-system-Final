# FindIt / UniFind — Lost & Found Frontend

A responsive React + Vite prototype inspired by the supplied FindIt UI reference and aligned with the Lost & Found Platform SRS.

## Requirements
- Node.js 20.19+ or 22.12+ recommended
- npm

## Run locally
```bash
npm install
npm run dev
```

## Production build
```bash
npm run build
npm run preview
```

## Included screens
- Landing page with search, district/category filters, feature highlights and sample items
- Browse/search with keyword search, Lost/Found tabs, category/district filters and sorting
- Item details with privacy reminders
- Multi-step Lost/Found report form with validation and review
- Real chat: message the reporter from any item page, inbox of all conversations, live updates
- Profile / My Items and Saved Items
- Notifications: bell + message badges, a notifications page, and a pop-up when something new arrives
- Login and registration UI
- About page
- Admin dashboard demo

## Backend
Start the backend first (see `../unifind-backend/README.md`). The API address is set in `.env` (`VITE_API_URL`). Without a backend the app shows sample data.

## Chat & notifications (how the frontend works)
- `src/components/ChatPage.jsx` – inbox + conversation + item panel. Open chats check for new messages every 4 s; the inbox refreshes every 8 s.
- `src/components/NotificationsPage.jsx` – list of notifications; clicking one opens the chat.
- `App.jsx` asks `/notifications/summary` every 15 s to update the bell / message badges and show a toast.
- All API calls are in `src/api.js`.

## Notes
- Accounts, reports, photos, saved items, chat and notifications are stored by the backend. Without it, only the sample items are shown.
- The admin dashboard is still a demo screen with fixed numbers.
- Sample item data is in `src/data/items.js`.
- Item images use remote Unsplash image URLs, so an internet connection is needed for them to load.
