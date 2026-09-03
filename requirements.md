You need to create a service which handles operations on products in an E-commerce system.
You can choose to use either FastAPI or Django. You may choose the database and any necessary technologies and packages needed.

1. Models
* Create a Product model. The model must contain at least:
- title
- description
- image
- unique product identifier (SKU)
- price
- category - link to a category model
* Create a category model. The model must contain at least:
- name
- parent - link to category model

2. Operations
* CRUD operations for both models.
* A "search" API endpoint which can search and filter products. You should design the endpoint in such a way
that a client could ask for all products matching a certain name/SKU; within a price range, or under a certain
category. You may add additional filters.

Guidance:
1. We prefer features with small but carefully designed scope. Think of it as a service that will hit production.
2. Include unit tests for the search functionality. No unit tests are required for the rest of the application.
3. You can use AI assistants for the home assignment. Be prepared to code a small feature on-site without AI
assistants but with the help of the official documentation/StackOverflow and the interviewers as pair-programmers.
4. We’ll expect a running project at the time of presentation.