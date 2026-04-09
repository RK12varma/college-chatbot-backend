# CollegeAI Frontend

This frontend is the React application for the CollegeAI chatbot system. It provides the user interface for student login, OTP verification, password recovery, the Data Science chatbot, and the admin dashboard.

## What This App Includes

- User authentication flows:
  - Login
  - Registration
  - OTP verification
  - Forgot password
  - Reset password
- Role-based protected routes for students and admins
- Chat interface for asking department-related questions
- Chat history and session management
- Downloadable PDF and document support from chatbot responses
- Admin dashboard for:
  - Viewing platform statistics
  - Uploading and indexing documents
  - Scraping department URLs
  - Managing users
  - Viewing audit logs

## Tech Stack

- React 19
- Vite 5
- React Router
- Axios
- Tailwind CSS
- React Markdown

## Project Structure

```text
frontend/
|-- public/                 Static assets
|-- src/
|   |-- components/         Shared UI and route guards
|   |-- components/admin/   Admin dashboard sections
|   |-- layouts/            Layout helpers
|   |-- pages/              App pages such as Login, Chat, Admin
|   |-- services/           API configuration and HTTP helpers
|   |-- App.jsx             Main route setup
|   |-- main.jsx            App entry point
|   `-- index.css           Global styles
|-- package.json
`-- vite.config.js
```

## Routes

### Public Routes

- `/` - Login page
- `/login` - Login page
- `/register` - Create a new account
- `/verify-otp` - Verify account OTP
- `/forgot-password` - Request password reset
- `/verify-reset-otp` - Verify reset OTP
- `/reset-password` - Set a new password

### Protected Routes

- `/chat` - Chat interface for `student` and `admin` roles
- `/admin` - Admin dashboard for `admin` role only

## Prerequisites

Before running the frontend, make sure you have:

- Node.js 18 or later
- npm
- The backend API running locally

## Installation

From the `frontend` folder:

```bash
npm install
```

## Running the App

Start the development server:

```bash
npm run dev
```

Then open the local URL shown by Vite, usually:

```text
http://localhost:5173
```

## Available Scripts

- `npm run dev` - Start the Vite development server
- `npm run build` - Create a production build
- `npm run preview` - Preview the production build locally
- `npm run lint` - Run ESLint checks

## Backend Connection

The frontend currently uses a hardcoded backend URL in `src/services/api.js`:

```js
baseURL: "http://127.0.0.1:8000"
```

Make sure the backend is running on that address and port. If your backend runs somewhere else, update that file before starting the app.

The frontend expects the backend to provide endpoints such as:

- `/auth/login`
- `/auth/register`
- `/auth/refresh`
- `/chat/ask`
- `/chat/sessions`
- `/document/pdfs`
- `/admin/stats`
- `/admin/documents`
- `/admin/users`
- `/admin/audit-logs`

## Authentication Notes

- Access tokens are stored in `localStorage` under `token`
- Refresh tokens are stored in `localStorage` under `refresh_token`
- User role is used to control access to protected pages
- If an access token expires, the frontend tries to refresh it automatically

## Development Notes

- The navbar is hidden on `/chat` and `/admin` to make room for dashboard-style layouts.
- The API client automatically attaches the access token to authenticated requests.
- Markdown responses from the chatbot are rendered in the chat UI.
- Admin actions such as upload, scraping, role changes, and deletion depend on backend permissions.

## Common Setup Checklist

1. Start the backend server.
2. Open a terminal in `frontend`.
3. Run `npm install` if dependencies are not installed yet.
4. Run `npm run dev`.
5. Open the Vite URL in your browser.
6. Register or log in with an account.
7. Use an admin account if you want access to `/admin`.

## Future Improvements

A few changes would make this frontend easier to maintain:

- Move the API base URL to a Vite environment variable such as `VITE_API_URL`
- Add screenshots or GIFs for the main user flows
- Document expected backend response shapes for contributors
- Add frontend tests for route protection and key pages

## Contributing

When updating this frontend:

- Keep route protection aligned with backend roles
- Update this README if routes, scripts, or setup steps change
- Test both student and admin flows when making auth-related changes

## License

Add your project license here if the repository is intended for public use.
