// @ts-check
import {themes as prismThemes} from 'prism-react-renderer';

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'StarCitizen OrgBot Manual',
  tagline: 'Operator and tester documentation',
  favicon: 'img/favicon.ico',
  future: {v4: true},

  url: 'https://sielski666.github.io',
  baseUrl: '/StarCitizen-Discord-OrgBot/',

  organizationName: 'sielski666',
  projectName: 'StarCitizen-Discord-OrgBot',
  trailingSlash: false,

  onBrokenLinks: 'throw',
  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      ({
        docs: {
          sidebarPath: './sidebars.js',
          routeBasePath: '/',
          editUrl: 'https://github.com/sielski666/StarCitizen-Discord-OrgBot/tree/main/website/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      }),
    ],
  ],

  themeConfig:
    ({
      colorMode: {
        respectPrefersColorScheme: true,
      },
      navbar: {
        title: 'StarCitizen OrgBot Manual',
        logo: {
          alt: 'OrgBot',
          src: 'img/logo.svg',
        },
        items: [
          {
            type: 'docSidebar',
            sidebarId: 'tutorialSidebar',
            position: 'left',
            label: 'Docs',
          },
          {
            href: 'https://github.com/sielski666/StarCitizen-Discord-OrgBot',
            label: 'GitHub',
            position: 'right',
          },
        ],
      },
      footer: {
        style: 'dark',
        links: [
          {
            title: 'Docs',
            items: [
              {
                label: 'Quick Start',
                to: '/',
              },
            ],
          },
          {
            title: 'Community',
            items: [
              {
                label: 'Discord',
                href: 'https://discord.com',
              },
            ],
          },
          {
            title: 'More',
            items: [
              {
                label: 'Repository',
                href: 'https://github.com/sielski666/StarCitizen-Discord-OrgBot',
              },
            ],
          },
        ],
        copyright: `Copyright © ${new Date().getFullYear()} StarCitizen OrgBot contributors.`,
      },
      prism: {
        theme: prismThemes.github,
        darkTheme: prismThemes.dracula,
      },
    }),
};

export default config;
