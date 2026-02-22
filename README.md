# College Chatbot Backend

## Introduction

The College Chatbot Backend is a Node.js application designed to provide automated responses and support for college-related queries. It manages user interactions, authentication, and integrates with OpenAI’s services for natural language responses. The backend supports user registration, login, and persistent chat history, making it suitable for deployment as the foundation of a college assistance chatbot.

## Features

- User registration and secure authentication
- JWT-based session management
- Chat interface with persistent message history
- Integration with OpenAI’s GPT models for generating answers
- REST API endpoints for chat and user management
- CORS support for client applications
- MongoDB database integration for storing users and messages

## Installation

To set up the backend locally, follow these steps:

1. Clone the repository:
   ```bash
   git clone https://github.com/RK12varma/college-chatbot-backend.git
   cd college-chatbot-backend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Set up the required environment variables. Create a `.env` file in the root directory with the following keys:
   ```
   PORT=5000
   MONGO_URL=your-mongodb-connection-string
   JWT_SECRET=your-secret-key
   OPENAI_API_KEY=your-openai-api-key
   ```

4. Start the server:
   ```bash
   npm start
   ```

The server will run on the port specified in the `.env` file.

## Requirements

- Node.js (version 14 or higher)
- npm (Node Package Manager)
- MongoDB instance (local or cloud)
- OpenAI API key

## Usage

Once installed and running, the backend exposes several REST API endpoints to manage users and chat functionality.

### User Flow

- Register a new account via the registration endpoint.
- Log in using the login endpoint to receive a JWT token.
- Use the token to authenticate and send chat messages.
- Retrieve past chat history.

### API Endpoints

#### User Registration (POST /api/register)
Registers a new user with a username and password.

```api
{
    "title": "User Registration",
    "description": "Register a new user with username and password",
    "method": "POST",
    "baseUrl": "http://localhost:5000",
    "endpoint": "/api/register",
    "headers": [
        {
            "key": "Content-Type",
            "value": "application/json",
            "required": true
        }
    ],
    "queryParams": [],
    "pathParams": [],
    "bodyType": "json",
    "requestBody": "{\n  \"username\": \"john_doe\",\n  \"password\": \"securePassword123\"\n}",
    "responses": {
        "201": {
            "description": "User registered successfully",
            "body": "{\n  \"message\": \"User registered successfully\"\n}"
        },
        "400": {
            "description": "User already exists",
            "body": "{\n  \"error\": \"User already exists\"\n}"
        }
    }
}
```

#### User Login (POST /api/login)
Authenticates a user and returns a JWT token.

```api
{
    "title": "User Login",
    "description": "Authenticate user and return JWT token",
    "method": "POST",
    "baseUrl": "http://localhost:5000",
    "endpoint": "/api/login",
    "headers": [
        {
            "key": "Content-Type",
            "value": "application/json",
            "required": true
        }
    ],
    "queryParams": [],
    "pathParams": [],
    "bodyType": "json",
    "requestBody": "{\n  \"username\": \"john_doe\",\n  \"password\": \"securePassword123\"\n}",
    "responses": {
        "200": {
            "description": "Login successful, JWT token returned",
            "body": "{\n  \"token\": \"<jwt-token>\"\n}"
        },
        "400": {
            "description": "Invalid credentials",
            "body": "{\n  \"error\": \"Invalid username or password\"\n}"
        }
    }
}
```

#### Send Chat Message (POST /api/chat)
Send a message to the chatbot and receive a response.

```api
{
    "title": "Send Chat Message",
    "description": "Send a message and receive a chatbot response",
    "method": "POST",
    "baseUrl": "http://localhost:5000",
    "endpoint": "/api/chat",
    "headers": [
        {
            "key": "Authorization",
            "value": "Bearer <jwt-token>",
            "required": true
        },
        {
            "key": "Content-Type",
            "value": "application/json",
            "required": true
        }
    ],
    "queryParams": [],
    "pathParams": [],
    "bodyType": "json",
    "requestBody": "{\n  \"message\": \"What courses are offered in Computer Science?\"\n}",
    "responses": {
        "200": {
            "description": "Chatbot response returned",
            "body": "{\n  \"response\": \"The Computer Science department offers various undergraduate and postgraduate courses including...\"\n}"
        },
        "401": {
            "description": "Unauthorized access",
            "body": "{\n  \"error\": \"Unauthorized\"\n}"
        }
    }
}
```

#### Get Chat History (GET /api/messages)
Retrieve the user’s chat history.

```api
{
    "title": "Get Chat History",
    "description": "Retrieve the authenticated user's chat history",
    "method": "GET",
    "baseUrl": "http://localhost:5000",
    "endpoint": "/api/messages",
    "headers": [
        {
            "key": "Authorization",
            "value": "Bearer <jwt-token>",
            "required": true
        }
    ],
    "queryParams": [],
    "pathParams": [],
    "bodyType": "none",
    "requestBody": "",
    "responses": {
        "200": {
            "description": "Chat history returned",
            "body": "{\n  \"messages\": [\n    { \"message\": \"Hi\", \"role\": \"user\" },\n    { \"message\": \"Hello! How can I help you today?\", \"role\": \"bot\" }\n  ]\n}"
        },
        "401": {
            "description": "Unauthorized access",
            "body": "{\n  \"error\": \"Unauthorized\"\n}"
        }
    }
}
```

## Configuration

Configuration is managed through environment variables. The following variables must be set:

- `PORT`: The port on which the server runs (default: 5000).
- `MONGO_URL`: MongoDB connection string.
- `JWT_SECRET`: Secret key for JWT signing.
- `OPENAI_API_KEY`: API key for OpenAI integration.

These can be set in a `.env` file in the project root. Example:

```
PORT=5000
MONGO_URL=mongodb://localhost:27017/college-chatbot
JWT_SECRET=my-secret-key
OPENAI_API_KEY=your-openai-key
```

---

For support or contributions, please refer to the repository issues or submit a pull request.
