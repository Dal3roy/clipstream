# Clipstream architecture

GitHub renders the Mermaid diagrams below directly.

## 1. System overview

```mermaid
flowchart LR
    user([User browser])

    subgraph Frontend
        swa[Azure Static Web Apps<br/>HTML / CSS / JS]
    end

    subgraph API["API (Azure App Service, FastAPI)"]
        api[Login, feed, comments, likes, upload URLs]
    end

    subgraph Data["Data"]
        cosmos[(Cosmos DB<br/>videos · comments · likes · users)]
        rawblob[(Blob: raw uploads)]
        outblob[(Blob: converted videos)]
    end

    subgraph Processing["Event-driven processing (Azure Functions)"]
        conv[Conversion<br/>FFmpeg → MP4 renditions]
        trans[Transcription]
    end

    subgraph AI["Azure AI services"]
        lang[AI Language<br/>sentiment]
        speech[AI Speech<br/>speech-to-text]
    end

    cdn[Azure Front Door / CDN]

    user -->|pages| swa
    user -->|API calls| api
    user -->|upload file via SAS URL| rawblob
    user -->|stream video| cdn

    api --> cosmos
    api -->|sentiment on new comment| lang

    rawblob -->|blob trigger| conv
    conv --> outblob
    conv --> trans
    trans --> speech
    trans -->|transcript + status ready| cosmos

    outblob --> cdn
```

## 2. Upload flow

Video bytes never pass through the API. The browser uploads straight to Blob Storage, and processing runs in the background.

```mermaid
sequenceDiagram
    actor U as User
    participant B as Browser
    participant A as API (App Service)
    participant C as Cosmos DB
    participant R as Blob (raw)
    participant F as Functions
    participant S as AI Speech

    U->>B: Choose file, enter title
    B->>A: POST /videos/upload-url
    A->>C: Create video (status: processing)
    A-->>B: videoId + SAS upload URL
    B->>R: PUT file (SAS)
    R-->>F: Blob trigger
    F->>F: Convert to MP4 renditions
    F->>R: Write renditions to converted container
    F->>S: Transcribe audio
    S-->>F: Transcript
    F->>C: Update video (status: ready, renditions, transcript)
    B->>A: GET /videos/{id} (polling)
    A->>C: Read video
    A-->>B: status: ready
```

## 3. Comment flow (with sentiment)

```mermaid
sequenceDiagram
    actor U as User
    participant B as Browser
    participant A as API
    participant L as AI Language
    participant C as Cosmos DB

    U->>B: Post comment
    B->>A: POST /videos/{id}/comments
    A->>L: Analyse sentiment of text
    L-->>A: label + scores
    A->>C: Insert comment (with sentiment)
    A-->>B: Comment with sentiment label
    B-->>U: Show comment and label
```

## 4. Like flow

```mermaid
sequenceDiagram
    actor U as User
    participant B as Browser
    participant A as API
    participant C as Cosmos DB

    U->>B: Tap like
    B->>A: POST /videos/{id}/like
    A->>C: Create likes doc (id = videoId:userId)
    alt Already liked (409 conflict)
        A-->>B: Success, count unchanged
    else New like
        A->>C: Patch video likeCount +1
        A-->>B: Success, new count
    end
```

## Container summary

| Container | Partition key | Used by |
|---|---|---|
| `videos` | `/id` | API (feed, upload), Functions (status, renditions, transcript) |
| `comments` | `/videoId` | API (post, list, sentiment summary) |
| `likes` | `/videoId` | API (like, unlike, "did I like this?") |
| `users` | `/id` | API (login) |
