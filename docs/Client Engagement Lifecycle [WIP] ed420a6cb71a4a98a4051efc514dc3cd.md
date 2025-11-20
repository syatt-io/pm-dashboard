# Client Engagement Lifecycle [WIP]

**Table Of Contents**

## 0. Preface

The following is a first attempt at defining the full client lifecycles and various touchpoint with the various teams & departments. That said, it’s important to read & internalize the following 2 things before getting into the lifecycle as the following is (hopefully) a good reference point but the these 2 are how we make the daily, difficult & creative decisions:

1. [Our Culture, Ethos & Core Values  ](https://www.notion.so/Our-Culture-Ethos-Core-Values-c0ab827be84a4b86bdbc9d728566ca58?pvs=21) 
2. [Our Guiding Principles [WIP]](https://www.notion.so/Our-Guiding-Principles-WIP-c35a44d121964d079f53a752a092122c?pvs=21)

## 1. Sales Scoping & Estimation

During the sales process we want to make sure we really understand/diagnose our potential client’s situation and think about a high level solution to achieve their goals. 

To do this, once the prospect is qualified, the delivery lead (**Mike**), the **PM**, **UX lead**, and a **technical lead** (or 2, depending on the needs) familiar with the likely platform should be engaged and the following should occur:

1. Internal meeting for the BD lead to share any information gathered about the prospect and the opportunity with the team (30-60min, led by the BD lead)
2. Meeting with the client and above people to discuss the **project & business drivers, pain points, aspirations, goals**, etc. (~60min, led by the BD lead)
3. Follow-up with the prospect for a more in-depth **technical chat**, [this doc](https://docs.google.com/document/d/1DHRv8vrHfq66OY0YOvglojnbdHHlQVeTzvs57FvUQas/edit#heading=h.56r0zgqgtnf4) can be used as a starting point for questions (~60min, led by the tech lead)
4. Calls should be recorded.  Lot’s of things are happening in these meetings, and this gives you the ability to reference conversation after the fact.  
5. During the above calls, the team should do their best to listen for and document any customizations that’ll likely be needed for the build, along with “outliers to baselines” or norms with respect to design, process, testing or integrations needed. Here’s an [old example from Cosmo](https://docs.google.com/document/d/1mm7aGVXUv4kiEYYVIpvDNwQZ1h-ScTWdZKcRB_XsReY/edit), and [another for Whitebird](https://docs.google.com/document/d/1_myiu9xTBwlaWvKTdMM6w3q22TB_qfg3PqJsjo5j1bA/edit#heading=h.594qh7s806fm), I’m sure we can create a better template for this.
6. Considering the above scope, any yellow/red flags, and the baseline of hours for the given platform, we can now guesstimate hours for the project, here’s an example of notes from [Cosmo](https://docs.google.com/spreadsheets/d/11hVu3X1LmXUxYyc8iPT66iLk-Im76iejzo0vXURE1n0/edit#gid=0).

🎉 Engagement is confirmed 🥳

## 2. Kickoff & Project Setup

Once the agreement is signed, the following things should take place:

- Assignment of team
- Internal Kickoff with the BD lead & team
- Creation of a Jira project and import ***standard*** operational & feature epics (**TODO**: link to standard epics)
- Schedule an external kickoff with the client (one full day in-person or two 2-3h sessions online)
- Create and send a kickoff agenda ([agenda template](https://docs.google.com/document/d/1rzWmjY0XzjZj0K1XI0pO9yA1HgQ2fz9c-JFcuRRRU_c/edit#heading=h.y2cl9a66fn9p)) to all customer stakeholders (ideally business lead, marketing/ecommerce lead, technical lead) and internal team.
- Create the starting project plan template (example: [Webs](https://docs.google.com/spreadsheets/d/10ycM8IC_4uqoyVoWudy1g1wG2JYlpQsTy7CfTKDeRm0/edit#gid=1713937810))

### Kickoff Meetings

The goals of the discovery:

- Get both teams acquainted to each other
- Understand the client’s strategy, landscape, business & project drivers
- Better understand and dig into the unique problems
- Help the client understand what the high level process looks like & what to expect

There should be an MC for the kickoff to keep things moving, ask questions (everyone is welcome and encourage to do so) and to stop/discourage on-the-spot solution’ing.

The meeting should be recorded.  This is helpful for other / future stakeholders, or reference (lots of ground covered in these meetings)

## 3. Discovery

The goal of a deep-dive discovery is to better understand our client, their competitive landscape, as well as their target demographics and value proposition (why do their customers choose them) to better define the online experience that’s part of the bigger customer journey. Some of this research should ideally be done upfront before the site’s user experience starts to be defined but the actual UI (wireframes & designs) would ideally be created iteratively within the build process to reduce the time to market. 

### Upfront Research Activities & Outputs

1. **Research**: getting a much better idea of our , some activities & outputs:
    1. Client Interviews
    2. End-user (customer) interviews
    3. Competitive analysis
    4. Funnel & Behavioural Analytics review
    5. Persona development
    6. Experience Mapping
    7. Taxonomy review 
    8. UX Review (Visual / Benchmarking)
2. Defining the **goals/outcomes** we would like to achieve with this project (ideally, qualitative and quantitative)
3. Defining the technical, UX and other **risks & challenges** to achieving said goals.
4. Defining the “solution architecture” for the various systems & 3rd party apps 
5. Defining the system architecture diagram for the various required integrations
6. Defining the Brand
    1. Mood Boards
    2. Brand Voice
    3. Brand / Style Guide
7. Taxonomy definition
8. Defining the **project specific epics** based on customizations, 3rd party needs & integrations

## 4. Design & Build

The reason we strongly believe in iterative development is the **feedback loop** - we want to get the client to see and test each page/feature as quickly as possible as there are *always* assumptions made on both side that are incorrect. As such, as soon as there’s a design for a page (or component) that the client is good with, we start building it in the browser. 

**Note**: If the client is not looking at their site in progress as each piece is done, something is going wrong and will likely cause issues later 🚩.

### Iterative UX/UI outputs

1. Page/Feature/Component based discovery
2. Page/Feature/Component based Wireframes 
3. Page/Feature/Component based high fidelity designs 
—> Once one is ready and there’s general, directional agreement, it moves to development

**Important** **Note**: These assets don’t have any value in and of themselves other than getting us one step closer to the digital experience we’re trying to build. As such, there isn’t a concept of a “final sign-off” of a pixel perfect design - more of a directional general agreement. Once the design makes its way to getting built in the browser certain changes may be needed or recommended, even if they sway from the original designs.

### Iterative Development & Integrations

As mentioned above, the high level goal of this phase is to build out the pages & features defined via designs as quickly and independently as possible to get client feedback & iterate as needed. Aside from the UX/UI stream of work outlined above, there can (and ideally should) be 3 other streams of work concurrently, to the degree that’s possible:

- Migrations & Integrations (back-end devs)
- 3rd Party App installations & configuration (PM or devs)
- Custom app or other customization (back-end and/or front-end devs)
- Theming/styling the UI (front-end devs)

Might look something like this:

![Screen Shot 2022-10-26 at 11.48.57 PM.png](Client%20Engagement%20Lifecycle%20%5BWIP%5D/Screen_Shot_2022-10-26_at_11.48.57_PM.png)

### Key principles/activities for a successful project

If/when at all possible, **One dedicated team** from start to finish, including the initial sales scoping & kickoff. The more context the team has the more likely they’ll make the right decisions.

Generally speaking we should be using **Scrum** practices for big projects - we’re not dogmatic about them and adjust as needed but they work well broadly. Other key points:

1. **Project Management**
    1. Setting the right **expectations & accountabilities** with the client from the beginning (e.g. they need to own their responsibilities, scope will shift throughout the project and we discuss as they do, etc - **TODO**: add template)
    2. [**Story Mapping](https://www.digite.com/agile/story-mapping/)** is a great way to breakdown the project needs into smaller chunks (epics/user stories) to think through the big picture and build context.
    3. Create a **Risk Registry** of the biggest concerns of the project to be reviewed & updated for each sprint and used to prioritize sprints. (**TODO**: add template)
    4. Ensure any **project specific** **epics** needed for 3rd parties, customizations or other work to be done are in Jira.
        1. Epics should contain the context for the feature/page/component at a high level, along with requirements & testing notes.
    5. Ensure there’s a **project plan** with the first 2-3 sprints outlined (the rest will be defined as we go) - example: [Webs](https://docs.google.com/spreadsheets/d/10ycM8IC_4uqoyVoWudy1g1wG2JYlpQsTy7CfTKDeRm0/edit#gid=1713937810). This should be updated with each sprint.
    
    1. **Sprint report** sent to the client/project team after each sprint as well as Jon & Mike (**TODO**: add template)
    2. Update a **monthly report** of hours by discipline to compare to original baselines for awareness and getting better at baseline estimates in the future.
    3. A project **Notion page** should be created to highlight the more pertinent client, team, project, and high level solution details, example: [Snuggle Bugz](https://www.notion.so/Snuggle-Bugz-86b3207b7c5c4858bbd0fda438caec97?pvs=21). All of the documents in this section should be linked to on this page for reference.
2. **Team Meetings**
    1. Daily stand-up with the team to make sure everyone has enough context about what’s going on and blockers/issues are dealt with together.
    2. Weekly internal grooming sessions for discussing & refining the backlog, based on the priority sequence.
    3. Bi-weekly sprint retro & planning session. Goals:
        1. Review what was completed the previous sprint and ask each team member if anything could be improved.
        2. Prioritize the tickets for the upcoming sprint. Note: ideally the tickets assigned to the next sprint are actionable at the start of the sprint and can be finished before the sprint ends. If the ticket needs to span more than 2 weeks, ideally it should be broken down into smaller chunks.
3. **Client Meetings & Communication**
    1. Weekly meetings with the client for discussing requirements, priorities, blockers, and demo’ing what’s been completed. 
        1. There should be at least one developer to support in these meetings, more devs and/or UX support as needed.
        2. An Agenda should be created and shared with the team before the call - others may want to add/update topics.
        3. Meeting notes sent to all Syatt & Client project team members after each meeting.
    2. Communication shouldn’t be limited to these meetings - whenever a question comes up feel free to use email/slack or any other channel to ask, waiting for a weekly meeting slows things down.
    3. Communications should be as “public” as possible, internally or externally. I.e. if anyone has a question or comment about a project they should ask in the project slack channel if it’s internal or add others to the email thread if it’s to the client vs DM’s or 1-1 emails. As mentioned above, the more context the team has the more likely they’ll make the right decisions.
4. **Ticket Creation & Management**
    1. Tickets should *strive* to:
        1. Include enough context about the “why” for the ticket to need to exist (everyone should feel comfortable challenging the why as they see fit)
        2. Have enough context to be actionable before getting started (see point b)
        3. As small as possible (ideally, not take longer than a day or two to complete)
        4. Be testable
        5. Include a “definition of done” so it can be verified & tested easier
        6. Be a part of an epic, helps visualize & report on high level progress
    2. While the PM “owns” the tickets in a way, the entire team should feel comfortable creating new ones as they see fit, asking clarifying questions and grooming everything together to ensure the right questions are asked and the necessary information is included.
    3. Everyone should ensure they update their ticket status & assignment as things move along
    4. Everyone should be trying to get tickets off their plates asap (tickets shouldn’t sit in progress) to get things tested & into the feedback loop.
    5. Also see the [Developer Playbook](https://www.notion.so/Developer-Playbook-91f55f6b9a774cfb9b7e5af06210348b?pvs=21) for some more helpful context.
5. **QA & UAT** 
    
    [How We Test Our Work (QA & UAT)](https://www.notion.so/How-We-Test-Our-Work-QA-UAT-1a76b885ac884bb4abeb4a74b49d4f67?pvs=21)
    

# 5. Launch

### Launch Prep

- End to end testing
- Analytics (GA/GTM)
- SEO
    - 301 Redirects
    - Schema Markup
    - Vanity URLs
    - Canonical Tags
- Sitemaps
- Accessibility Review

### Launch Checklist

- Shopify
    - 
- VTEX
    - 

# 6. Support & Growth

### Overview

### Continuous Discovery

### Performance (Speed) Management

### Roadmaps

### Testing

### Metrics