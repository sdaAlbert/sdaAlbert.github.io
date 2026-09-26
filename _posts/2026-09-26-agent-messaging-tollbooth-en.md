---
title: "After the Lobster Hype: A Critique of Marketing-First Agent Startups"
date: 2026-09-26
permalink: /posts/agent-messaging-tollbooth/en/
lang: en
translations:
  zh: /posts/agent-messaging-tollbooth/
  en: /posts/agent-messaging-tollbooth/en/
author_profile: false
read_time: true
excerpt: "Using Photon as a case study, this essay asks whether messaging adapters can become Agent infrastructure, how open-source products make money, and who pays for the current hype."
tags:
  - Industry Observation
---

During the lobster craze, everyone was talking about Agents moving into chat apps and getting things done.

Installation guides, model bills, Mac minis, and automation demos appeared everywhere. Give an Agent enough permissions, the story went, and soon everyone would have a digital employee.

The products were still looking for durable use cases. The narrative had already arrived from the future.

Today’s guest is [Photon](https://photon.codes/). I am not singling it out to pick a fight. I want to use it as a sample of the wry, “ship fast” style of application startup. I was once taken in by this kind of startup marketing myself. I am writing this to offer a little distance and a more critical way to look at it.

Photon is a “chat switchboard.” Developers connect their own Agents to Photon, which then connects them to messaging apps such as iMessage. Users can assign tasks and receive replies as if they were texting someone.

You may have seen [“Clawdbot Is a Middle-Aged-Man Hype Campaign Orchestrated by Musk”](https://m.aitntnews.com/newDetail.html?newId=22138) or [“OpenClaw Is Worse Than a Dog”](https://funeralai.cc/test/r10/doubao-seed-2-1-pro-260628/articles/067/). In broad strokes, those pieces argue that the lobster’s innovation is about as impressive as using a phone at the gym to ask an Agent to write code. What a joke.

But our product connects Agents to iMessage, so surely that is different. Here is the question: **How does a useful piece of messaging plumbing become infrastructure for the Agent era?**

## Agents may be useful without every new entry point being useful

Photon’s vision story is smooth: Agents are trapped in developer tools and new apps; ordinary people should not have to download another app; Mom can talk to an Agent directly in iMessage. [“Introducing Spectrum”](https://photon.codes/blog/introducing-spectrum)

Its blog offers plenty of possible use cases: personal assistants, concierge services, customer support, coding partners, and calendar assistants. It also features MimiClaw, a tiny-chip-based assistant that can remind you about tasks, answer questions, remember things you have said, and reach you through iMessage. [Photon on Agent use cases](https://photon.codes/blog/photon-vs-sendblue-choosing-an-imessage-api-for-ai-agents) · [The MimiClaw case](https://photon.codes/blog/how-mimiclaw-put-a-pocket-ai-assistant-on-imessage)

But Photon’s core pitch to developers is less “an Agent in iMessage is cool” and more: stop maintaining a Mac, dealing with Apple accounts, and forwarding messages; connect to Spectrum and launch. That sounds a lot like infrastructure, but it raises an awkward question.

If a product has not found users, connecting it to five chat apps only gives an unused Agent five more doors. If it already has users, they will stay because the Agent gets things done, not because of which messaging pipe sits behind it.

And “iMessage is where everyone spends their day”—well, probably?

Shortly before this article was written, Tencent announced that QClaw would shut down in December 2026 and directed users to migrate to WorkBuddy. Tencent said the decision reflected business adjustments and resource consolidation. [QClaw shutdown report](https://www.ithome.com/1/006/528.htm) · [Caixin report](https://companies.caixin.com/2026-09-24/102488349.html)

Tencent is still building Agents. It is choosing to consolidate products and resources around a different entry point.

If a large company can reorganize its Agent product, user entry point, and team resources, why assume an independent middle layer can stay in the middle forever? Today you save a customer from writing a bit of code. Tomorrow a framework may include that code out of the box.

What can a small company do? Make quick money with marketing, build an audience, and wait to be acquired!

## Marketing first: sell connectivity, pitch a civilizational shift

On pricing: developers can download Spectrum’s free code, provide their own hardware and number, and maintain the connection themselves. Or they can pay Photon to host it and manage the line. Its website lists Pro at $25 per month and Business at $250 per dedicated iMessage line per month. [Pricing](https://photon.codes/pricing)

Charging for this is not absurd. Hosting, phone lines, and maintenance time have real costs. Running a Mac yourself is not free either: BlueBubbles bridging, permissions, and system updates all need care. Photon’s own comparison article makes its pitch plainly: self-host for local experiments; buy a managed line for a production service. [BlueBubbles vs. Photon](https://photon.codes/blog/the-path-from-bluebubbles-to-production-imessage-agents-on-photon)

The service maintains a complex, fragile messaging path that can be affected by changes to Apple’s platform. It is more than leaving a Mac running in a server room. Photon’s engineering post describes how its shared lines must decide which Agent owns each message among many numbers and conversations. The old system suffered silent disconnects, routing errors, and peak-time delays. The team later changed message intake to write events to a durable log before resolving ownership and dispatching them. [The shared-routing rebuild](https://photon.codes/blog/how-we-rebuilt-our-shared-imessage-routing-to-handle-10m-messages-a-day) For a product with real users and messages it cannot afford to lose, handling failures, staying online, and maintaining the lines can be worth far more than hastily assembling a bridge of its own.

Build a bridge, sell it, and charge a toll. Fair enough.

But as I said, the hardest part of explaining a toll is answering: why must everyone cross your bridge?

That is why Photon’s blog keeps announcing iMessage integrations with new frameworks: Hermes, NanoClaw, Mastra, Vercel Chat SDK, Convex. Connect one framework, publish a post saying “now it can send iMessages”; then move on to the next one and publish again.

A growing ecosystem and a longer list of frameworks do not automatically mean progress. For example, a [study of developer practices in Agent frameworks](https://arxiv.org/abs/2512.01939) analyzed ten frameworks and nearly 12,000 developer discussions. It found that developers often struggle to tell which framework fits their needs as the choices keep growing.

Frameworks are supposed to make development easier. Yet many Agent frameworks wrap model calls, tools, memory, and workflows in separate abstractions, then give each layer its own concepts and APIs. Developers must first decide which stack to bet on, then learn its conventions. The study repeatedly surfaces another burden: after a framework upgrade, developers may have to revisit tool interfaces, state management, and deployment configuration.

That is the funny part of this “ecosystem boom.” Every company says it is lowering the barrier to development, while developers end up with a dozen frameworks, dozens of integrations, and a long list of version-compatibility problems. Under the label “Agent,” pilots, wrappers, connectivity layers, and products that solve real business problems can all end up on the same ecosystem poster.

In 2025, Gartner warned that many Agent projects were still hype-driven early experiments. It predicted that more than 40% of Agent projects could be canceled by the end of 2027 because of cost, unclear business value, or inadequate risk controls. [Gartner’s forecast](https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-predicts-over-40-percent-of-agentic-ai-projects-will-be-canceled-by-end-of-2027)

AI is increasing the supply of things that can be shipped faster than the supply of things people want to keep using. [Research on slop in AI-assisted software development](https://arxiv.org/abs/2603.27249) Against that backdrop, every new framework integration makes Photon’s list look a little more like a flyer saying, “We already sit at the center of the ecosystem.”

Photon also says it handles tens of millions of iMessage API calls a day, and its blog lists names such as Rho, Vercel, Hermes, Ditto, and FlipText.

The public material does not break down whether those names are paying customers, partners, integration examples, or community users. It also does not publish customer retention, renewal rates, or revenue mix. [Photon’s infrastructure article](https://photon.codes/blog/how-photon-built-one-of-the-most-stable-and-enterprise-ready-imessage-apis)

The numbers keep getting bigger, so the story has to get bigger too.

“We maintain a complex messaging channel for developers.”

“We bring Agents into everyone’s daily life!”

“We are infrastructure for the Agent era!”

There is another question that is easy to skip: when users message a hosted Agent, their messages pass through the provider’s infrastructure. Photon’s privacy policy lists TLS, encryption at rest, and access controls. When I checked, I could not find the specifics an employee had described on Reddit—that messages are cached for about a week and employees cannot access them. In a follow-up, the employee said access was restricted through policy and physical separation, rather than Photon being technically incapable of decrypting the messages. [Photon privacy policy](https://app.photon.codes/privacy-policy) · [Reddit discussion](https://www.reddit.com/r/hermesagent/comments/1uayr7v/cybersecurity_for_hermes_ios_ux_imessage_matrix/)

Someone in the thread suggested adding that employee statement to the privacy page. I checked, and as of this article’s publication, it still was not there.

## Open-source Agent startups: after releasing the code, what do you sell?

Photon releases the Spectrum SDK under the MIT license and sells hosted lines and cloud services. It is not alone. This is a familiar model in developer-tool startups: open the code to lower the barrier to trying it, then charge for hosting, collaboration, observability, governance, or support.

First, consider [Supabase’s discussion of whether to open-source a company](https://supabase.com/blog/should-i-open-source-my-company). Open source lets developers try a product, deploy it themselves, inspect the code, and contribute fixes or integrations. It also creates maintenance work. If the product succeeds, cloud providers with stronger distribution may host competing versions. The lesson for founders: open source can open the door and give a community room to improve the product; it cannot protect the business behind that door.

Then there is [n8n’s explanation of its Sustainable Use License](https://blog.n8n.io/announcing-new-sustainable-use-license/). n8n chose fair-code: people can view, modify, and use the source within certain limits, but commercial use has boundaries. Its reasoning is straightforward: if cloud providers capture the value created by an open-source project, the original team may not earn enough to keep maintaining it. Open-source startups often have to balance broad adoption through openness against limiting others’ ability to commercialize the work for free.

For an Agent startup, the question becomes practical: open source lets users download the Agent and get it running on their own computers. When will they pay? Usually when an experiment becomes part of daily work: the Agent has to stay online all night, teams need to share it, accounts and permissions must stay separate, and someone must be able to find out what it read and did when something goes wrong. A team that handles these responsibilities reliably may be able to turn a project into a service.

But if the reason to pay is only “one-click deployment” or “we connect a few models and tools for you,” cloud platforms and model providers may bundle that feature once demand is proven. Other teams can copy an open-source implementation too. Stars and downloads show that people are willing to try something; they do not prove that anyone will renew. The better question is what a customer would lose by leaving after putting real work on the service: dependable operations, team workflows, or clear accountability. Without those, hosted cloud is convenience. With them, it starts to look like a business people can pay for over time.

Photon’s position is clear, but it still lives under the shadow of larger companies. iMessage adds a special constraint: access depends on Apple’s closed platform. Photon can maintain the messaging lines more professionally than an individual developer, but it cannot decide what Apple will permit, block, or change in the future. Supporting multiple platforms can reduce dependence on one channel, but it also invites a fair customer question: am I buying long-term communications infrastructure, or a hosted service that happens to save me time wiring things together today?

Open source is not automatically a moat. It is an excellent way to bring people in.

## Who pays for the Agent bubble?

Photon’s current service can save development time and remove the burden of maintaining messaging lines. There is nothing inherently wrong with charging for that. Similar services include [Sendblue](https://www.sendblue.com/), [LoopMessage](https://loopmessage.com/), and [Claw Messenger](https://www.clawmessenger.com/). They are not identical products, and they should not all be dismissed as scams. Their business structures do share a pattern: someone else builds the Agent, Apple or another platform controls the chat app, and an intermediary delivers messages and returns replies in exchange for a convenience fee.

“Let software send and receive messages over an API” has nothing inherently to do with Agents. When Twilio was founded in 2008, its business was turning complex telecom networks into cloud services developers could call. Its programmable messaging APIs have long supported customer-service notifications, appointment reminders, and two-way communication. [Twilio’s history](https://www.twilio.com/en-us/company) · [Twilio programmable messaging materials](https://investors.twilio.com/static-files/ab80b58f-a26d-473e-956c-4fccb39a14d0)

Photon brings that old CPaaS business into the present and focuses on a narrow channel: iMessage, which lacks a general public bot API and takes device and line maintenance to access. There is real engineering work here. But does adding the word “Agent” suddenly make this old business look like a glamorous older woman?

And compared with other projects, isn’t it more reliable to make money from developers than from consumer customers? If success depends on where you stand in the value chain, the AI apps at the bottom—unable to capture much value and vulnerable to every model update—might as well position themselves here, teach developers not to fall behind, and charge them to try the new thing!

Who is building infrastructure, and who is paying tuition for the boom? It is a sad cycle.

For those who do take this path, I hope it is not an unproven startup founder with no validated business model. I hope it is someone who has already made money in a traditional industry and wants to unlock what Agents can do—someone who sees that iMessage can now be connected and thinks, “How unbelievable!” Then, after paying for models, cloud services, data, and distribution at every layer, at least the Agent has created real value for that person.

---

*Editorial note: This article is the author’s commentary and analysis of business models based on public information. The criticism of Photon expresses opinion and is not a factual allegation that Photon or its employees have acted illegally, fraudulently, or with intent to mislead. Statements about product features, customer examples, call volume, reliability, and privacy practices are based on the linked public sources; company-reported figures are identified as such. These details may change. Readers should consult the cited pages and any later statements from the companies for updates.*
